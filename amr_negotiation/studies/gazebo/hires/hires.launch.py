"""Gazebo episode with a high-resolution oblique camera; frames saved as PNG by frame_saver.py."""
import os, re
from pathlib import Path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, EmitEvent, ExecuteProcess, OpaqueFunction, RegisterEventHandler, SetEnvironmentVariable
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from amr_negotiation import gzworld
from amr_negotiation.geometry import load_scenario


def setup(context):
    lc = lambda n: LaunchConfiguration(n).perform(context)
    sc = load_scenario(lc("scenario"))
    out = Path(lc("output_dir")); out.mkdir(parents=True, exist_ok=True)
    tag = f"{sc.name}_{lc('policy')}_s{lc('seed')}"
    world, bridge = gzworld.write_world(sc, out / "worlds" / tag, overhead_camera=True, camera_size=(4, 4))
    txt = Path(world).read_text()
    cx, cy, cz, pitch, fov = (float(lc(k)) for k in ("cam_x", "cam_y", "cam_z", "cam_pitch", "cam_fov"))
    w, h = int(lc("width")), int(lc("height"))
    txt = re.sub(r'<model name="overhead_camera"><static>true</static>\s*<pose>[^<]*</pose>',
                 f'<model name="overhead_camera"><static>true</static>\n      <pose>{cx} {cy} {cz} 0 {pitch} 1.5708</pose>', txt)
    txt = txt.replace("<horizontal_fov>1.25</horizontal_fov>", f"<horizontal_fov>{fov}</horizontal_fov>")
    txt = txt.replace("<width>4</width><height>4</height>", f"<width>{w}</width><height>{h}</height>")
    txt = txt.replace("<update_rate>10</update_rate>", "<update_rate>2</update_rate>")
    txt = txt.replace("<format>R8G8B8</format>", "<format>R8G8B8</format><anti_aliasing>8</anti_aliasing>")
    Path(world).write_text(txt)
    acts = [ExecuteProcess(cmd=["gz", "sim", str(world), "-s", "--headless-rendering"], output="log"),
            Node(package="ros_gz_bridge", executable="parameter_bridge", name="bridge",
                 parameters=[{"config_file": str(bridge), "use_sim_time": True}], output="log")]
    common = {"scenario": lc("scenario"), "use_sim_time": True}
    for a in sc.agents:
        acts.append(Node(package="amr_negotiation_ros", executable="agent_node", name=f"agent_{a.id}",
                         parameters=[{**common, "robot_id": a.id, "policy": lc("policy"), "rulebook": "",
                                      "policy_file": lc("policy_file"), "seed": int(lc("seed"))}], output="screen"))
    ref = Node(package="amr_negotiation_ros", executable="referee_node", name="referee",
               parameters=[{**common, "policy": lc("policy"), "output": str(out / f"{tag}.json")}], output="screen")
    acts.append(ref)
    acts.append(ExecuteProcess(cmd=["python3", "/hires/frame_saver.py", str(out / "frames")], output="screen"))
    acts.append(RegisterEventHandler(OnProcessExit(target_action=ref, on_exit=[EmitEvent(event=Shutdown(reason="done"))])))
    return acts


def generate_launch_description():
    models = "/opt/ros/jazzy/share/turtlebot3_gazebo/models"
    args = dict(scenario="", policy="cost_bid", policy_file="", seed="0", output_dir="/results",
                cam_x="4.0", cam_y="-2.0", cam_z="2.6", cam_pitch="0.95", cam_fov="1.0", width="3840", height="2160")
    return LaunchDescription([SetEnvironmentVariable("GZ_SIM_RESOURCE_PATH", models + ":" + os.environ.get("GZ_SIM_RESOURCE_PATH", ""))]
                             + [DeclareLaunchArgument(k, default_value=v) for k, v in args.items()]
                             + [OpaqueFunction(function=setup)])
