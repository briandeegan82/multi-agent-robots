#!/bin/sh
# High-resolution stills for Fig. 3(e,f): one Gazebo episode with a 3840x2160 oblique camera, frames saved as PNG.
# args: label scenario policy rulebook cam_x cam_y cam_z cam_pitch cam_fov ros_domain
# Fig. 3(e): run.sh e_single gz_s0 cost_bid - 1.0 -3.0 2.9 0.82 1.0 43        (frame t=32 s)
# Fig. 3(f): run.sh f_tjgoal gz_tjgoal_s0 fixed_priority - 4.0 -3.4 3.2 0.80 1.1 42   (frame t=29 s)
lab=$1; scn=$2; p=$3; rb=$4; D=$(cd "$(dirname "$0")" && pwd); S=${GZSCEN:-$HOME/studies/gzwp1/scen}
mkdir -p $D/out/$lab
RB=""; [ "$rb" != "-" ] && RB="rulebook:=$rb"
docker run --rm --gpus all -e ROS_DOMAIN_ID=${10} -e GZ_PARTITION=hires${10} -v $S:/scen -v $D:/hires -v $D/out/$lab:/results ${AMRNEG_IMAGE:-amrneg} \
  ros2 launch /hires/hires.launch.py scenario:=/scen/$scn.yaml policy:=$p $RB seed:=0 cam_x:=$5 cam_y:=$6 cam_z:=$7 cam_pitch:=$8 cam_fov:=$9 > $D/out/$lab/log.txt 2>&1
