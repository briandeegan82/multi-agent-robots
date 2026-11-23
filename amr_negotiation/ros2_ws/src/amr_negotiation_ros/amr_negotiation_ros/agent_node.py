"""ROS 2 negotiation agent: wraps amr_negotiation.agent.Agent for one Gazebo TurtleBot3 Waffle.

Pose comes from /<id>/ground_truth (world frame); the lidar scan is projected into the world
frame, points on the known map walls are removed and the rest are clustered into peer robots.
Negotiation messages are JSON on /amr_negotiation/bus with emulated latency/jitter/loss.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import rclpy
from geometry_msgs.msg import TwistStamped
from nav_msgs.msg import Odometry
from rclpy.clock import Clock, ClockType
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String

from amr_negotiation.agent import Agent, Perception
from amr_negotiation.geometry import load_scenario

LIDAR_X = -0.064
BUS = "/amr_negotiation/bus"
EVENTS = "/amr_negotiation/events"


def _yaw(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


def seg_dist(p, segs):
    a, b = segs[:, 0], segs[:, 1]
    ab = b - a
    t = np.clip(np.einsum("ij,nij->ni", ab, p[:, None, :] - a[None]) / np.maximum((ab * ab).sum(1), 1e-12), 0, 1)
    proj = a[None] + t[..., None] * ab[None]
    return np.linalg.norm(p[:, None, :] - proj, axis=2).min(1)


def cluster(points, gap=0.25, min_pts=3):
    out = []
    used = np.zeros(len(points), bool)
    for i in range(len(points)):
        if used[i]:
            continue
        grp = [i]
        used[i] = True
        k = 0
        while k < len(grp):
            d = np.linalg.norm(points - points[grp[k]], axis=1)
            new = np.where((d < gap) & ~used)[0]
            used[new] = True
            grp.extend(new.tolist())
            k += 1
        if len(grp) >= min_pts:
            out.append(points[grp])
    return out


class AgentNode(Node):
    def __init__(self):
        super().__init__("agent")
        self.declare_parameter("robot_id", "A")
        self.declare_parameter("scenario", "")
        self.declare_parameter("policy", "rule_based")
        self.declare_parameter("rulebook", "")
        self.declare_parameter("policy_file", "")  # JSON with extra policy keys (report_scale, bid_sigma, table, ...)
        self.declare_parameter("seed", 0)
        self.declare_parameter("rate", 20.0)
        self.declare_parameter("map_filter", 0.08)
        g = lambda n: self.get_parameter(n).value
        self.rid = g("robot_id")
        self.sc = load_scenario(g("scenario"))
        cfg = next(a for a in self.sc.agents if a.id == self.rid)
        policy = {"name": g("policy")}
        if g("rulebook"):
            policy["rulebook"] = g("rulebook")
        if g("policy_file"):
            policy.update(json.loads(Path(g("policy_file")).read_text()))
        if policy.get("noise_key") == "episode":
            policy.setdefault("noise_seed", int(g("seed")))  # same on every robot: both reproduce each other's noisy bid
        seed = int(g("seed")) * 1000 + sum(map(ord, self.rid))
        self.rng = np.random.default_rng(seed)
        self.agent = Agent(cfg, self.sc, policy, rng=np.random.default_rng(seed + 1))
        self.segs = np.array(self.sc.wall_segments(), float)
        self.map_filter = g("map_filter")
        self.comms = self.sc.comms
        self.pose = None
        self.points = np.zeros((0, 2))
        self.peers: list[tuple[float, float]] = []
        self.inbox: list[tuple[float, dict]] = []
        self.n_events = 0
        self.done_sent = False
        qos = QoSProfile(depth=50, reliability=ReliabilityPolicy.RELIABLE)
        self.cmd_pub = self.create_publisher(TwistStamped, f"/{self.rid}/cmd_vel", 10)
        self.bus_pub = self.create_publisher(String, BUS, qos)
        self.ev_pub = self.create_publisher(String, EVENTS, qos)
        self.create_subscription(Odometry, f"/{self.rid}/ground_truth", self.on_odom, 10)
        self.create_subscription(LaserScan, f"/{self.rid}/scan", self.on_scan, 10)
        self.create_subscription(String, BUS, self.on_bus, qos)
        self.create_timer(1.0 / g("rate"), self.on_tick)
        self.create_timer(1.0, self.on_hello, clock=Clock(clock_type=ClockType.STEADY_TIME))
        self.get_logger().info(f"{self.rid}: policy={policy} start_x={cfg.start_x} goal_x={cfg.goal_x}")

    def now(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def on_hello(self):
        self.ev_pub.publish(String(data=json.dumps({"agent": self.rid, "event": "hello", "t": self.now(),
                                                    "have_pose": self.pose is not None})))

    def on_odom(self, m: Odometry):
        p = m.pose.pose
        self.pose = (p.position.x, p.position.y, _yaw(p.orientation), m.twist.twist.linear.x)

    def on_scan(self, m: LaserScan):
        if self.pose is None:
            return
        x, y, th, _ = self.pose
        r = np.asarray(m.ranges, float)
        a = m.angle_min + m.angle_increment * np.arange(len(r))
        ok = np.isfinite(r) & (r > m.range_min) & (r < m.range_max)
        r, a = r[ok], a[ok]
        lx, ly = x + LIDAR_X * math.cos(th), y + LIDAR_X * math.sin(th)
        pts = np.stack([lx + r * np.cos(a + th), ly + r * np.sin(a + th)], 1)
        if len(pts):
            pts = pts[seg_dist(pts, self.segs) > self.map_filter]
        self.points = pts
        peers = []
        for c in cluster(pts):
            cx, cy = c.mean(0)
            d = math.hypot(cx - lx, cy - ly)
            if d > 1e-6:  # surface points are biased towards the observer
                cx += 0.1 * (cx - lx) / d
                cy += 0.1 * (cy - ly) / d
            peers.append((float(cx), float(cy)))
        self.peers = peers

    def on_bus(self, m: String):
        env = json.loads(m.data)
        if env["src"] == self.rid:
            return
        if self.rng.random() < self.comms.get("loss", 0.0):
            return
        delay = self.comms.get("latency", 0.0) + self.comms.get("jitter", 0.0) * self.rng.random()
        self.inbox.append((self.now() + delay, env["msg"]))

    def on_tick(self):
        if self.pose is None:
            return
        t = self.now()
        due = [msg for (tt, msg) in self.inbox if tt <= t]
        self.inbox = [(tt, msg) for (tt, msg) in self.inbox if tt > t]
        v, w, out = self.agent.step(t, self.pose, Perception(self.points, self.peers), due)
        for msg in out:
            self.bus_pub.publish(String(data=json.dumps({"src": self.rid, "msg": msg}, default=float)))
        cmd = TwistStamped()
        cmd.header.stamp = self.get_clock().now().to_msg()
        cmd.header.frame_id = f"{self.rid}/base_footprint"
        cmd.twist.linear.x = float(v)
        cmd.twist.angular.z = float(w)
        self.cmd_pub.publish(cmd)
        for e in self.agent.events[self.n_events:]:
            self.ev_pub.publish(String(data=json.dumps(e, default=float)))
        self.n_events = len(self.agent.events)
        if self.agent.mode == "DONE" and not self.done_sent:
            self.done_sent = True
            summary = {"agent": self.rid, "event": "summary", "t": t, "arrival": self.agent.done_t,
                       "yields": self.agent.n_yields, "msgs_sent": self.agent.msgs_sent,
                       "decisions": self.agent.decisions}
            self.ev_pub.publish(String(data=json.dumps(summary, default=float)))


def main():
    rclpy.init()
    node = AgentNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
