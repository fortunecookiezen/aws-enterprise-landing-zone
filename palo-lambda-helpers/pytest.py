#!/usr/bin/env python3
import os
import sys
sys.path.append(os.getcwd())
import palo_static_route
import palo_helpers
import logging

palo_mgt_ip = 'localhost'
user = 'admin'
password = 'MoOCloud123!'
try:
    api_key = palo_helpers.getApiKey(hostname=palo_mgt_ip, username=user, password=password)
except Exception as e:
    logging.error(f"unable to connect to {palo_mgt_ip} as user: {user} with password: {password}")
    logging.error(e)
    sys.exit(1)

# Create a test route
logging.info("-----CREATE-----------------")
palo_static_route.set_static_route(hostname=palo_mgt_ip, api_key=api_key, destination='10.251.0.0/16', next_hop='10.250.1.1', interface='ethernet1/2')

# Modify the next hop
logging.info("-----UPDATE1-----------------")
palo_static_route.set_static_route(hostname=palo_mgt_ip, api_key=api_key, destination='10.251.0.0/16', next_hop='10.250.1.2', interface='ethernet1/2')

# Modify the interface
logging.info("-----UPDATE2-----------------")
palo_static_route.set_static_route(hostname=palo_mgt_ip, api_key=api_key, destination='10.251.0.0/16', next_hop='10.250.1.2', interface='ethernet1/1')

# Delete the route
logging.info("-----DELETE-----------------")
palo_static_route.delete_static_route(hostname=palo_mgt_ip, api_key=api_key, destination='10.251.0.0/16')

