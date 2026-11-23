#!/bin/sh
# Gazebo S7 check with episode-keyed bid noise: args idx seed pol(s05|s10)
i=$1; s=$2; p=$3; D=$HOME/studies/noisekey; S=$HOME/amrneg_wp1/amr_negotiation/studies/gazebo/scen_all
lab=cost_bid_${p}_ep; mkdir -p $D/out/$lab; dom=$(( i + 60 ))
docker run --rm --name nk_$i -e ROS_DOMAIN_ID=$dom -e GZ_PARTITION=nk_$dom -v $S:/scen -v $D/pol:/pol -v $D/out/$lab:/results \
  -v $D/policies.py:/amr_negotiation/amr_negotiation/policies.py:ro \
  -v $D/agent_node.py:/amr_negotiation/ros2_ws/build/amr_negotiation_ros/amr_negotiation_ros/agent_node.py:ro \
  ${AMRNEG_IMAGE:-amrneg:wp1} \
  ros2 launch amr_negotiation_ros corridor.launch.py scenario:=/scen/gz_noise_s$s.yaml policy:=cost_bid policy_file:=/pol/$p.json seed:=$s record:=false > $D/out/$lab/log_s$s.txt 2>&1
echo "$i $s $p $? $(date +%T)" >> $D/progress.txt
