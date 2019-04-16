# palo_static_route.py
"""
This lambda manages static routes in a palo alto firewall
"""

# Initialise the aws cfn helper, all inputs are optional, this example shows the defaults
from crhelper import CfnResource
helper = CfnResource(json_logging=False, log_level='DEBUG', boto_level='CRITICAL')

try:
    # Init code goes here
    import moo_helpers
    import palo_helpers
    import xml.etree.ElementTree as ET
    from typing import Optional

    logger = moo_helpers.get_console_logger()
    # logger.setLevel('DEBUG')
    import logging


except Exception as e:
    helper.init_failure(e)


def get_matching_route_name(hostname, api_key, destination, next_hop,
                            interface, virtual_router='default') -> Optional[str]:
    """
    Test to see if a matching route exists on the virtual router
    :param string hostname: the IP or hostname for the palo management interface
    :param string api_key: the api key to access the palo (from palo_helpers.getApiKey)
    :param string destination: the cidr block of the route (ex. 10.0.0.0/8)
    :param string next_hop: the IP address of the next hop (ex 10.250.1.1)
    :param string interface: the name of the palo network interface (ex ethernet1/2)
    :param string virtual_router: the name of the palo virtual router (default: "default")
    :return: string route_name if matching route exists, else false
    """
    logger.debug(f"Looking for route on palo: {hostname} virtual_router: {virtual_router} destination: {destination}, "
                 f"next_hop: {next_hop}, interface: {interface}")
    xpath = f"/config/devices/entry[@name='localhost.localdomain']/network/virtual-router/" \
        f"entry[@name='{virtual_router}']/routing-table/ip/static-route/entry"
    logger.debug(f"XPATH: {xpath}")
    response_xml = palo_helpers.panGetConfig(hostname=hostname, api_key=api_key, xpath=xpath)
    result_dict = palo_helpers.XmlDictConfig(ET.XML(response_xml))
    # if no static routes exits, the library returns None
    if not result_dict['result']:
        return False
    entries = result_dict['result']['entry']
    # If only one static route exists, the library returns a dict. If multiples exist, it returns a list.
    if isinstance(entries, palo_helpers.XmlDictConfig):
        entries = [entries]  # put the single entry dict into a list
    logger.debug(f"ENTRIES: {entries}")
    # Now we can safely iterate over a list of entries, even if we only got one
    for entry in entries:
        if 'ip-address' not in entry['nexthop']:
            pass
        if destination == entry['destination'] and next_hop == entry['nexthop']['ip-address'] and \
                interface == entry['interface']:
            logger.debug(f"found matching route. Returning: {entry['name']}")
            return entry['name']
    logger.debug(f"no matching route found. Returning False")
    return False


def static_route_exists(hostname, api_key, destination, virtual_router='default') -> Optional[str]:
    """
    Test to see if a route with matching destination exists on the virtual router
    :param string hostname: the IP or hostname for the palo management interface
    :param string api_key: the api key to access the palo (from palo_helpers.getApiKey)
    :param string destination: the cidr block of the route (ex. 10.0.0.0/8)
    :param string virtual_router: the name of the palo virtual router (default: "default")
    :return: string route_name if matching route exists, else False
    """
    static_route_xpath = f"/config/devices/entry[@name='localhost.localdomain']/network/virtual-router/" \
        f"entry[@name='{virtual_router}']/routing-table/ip/static-route"
    xpath = static_route_xpath + '/entry'
    response_xml = palo_helpers.panGetConfig(hostname=hostname, api_key=api_key, xpath=xpath)
    result_dict = palo_helpers.XmlDictConfig(ET.XML(response_xml))
    # if no static routes exits, the library returns None
    if not result_dict['result']:
        # No static routes exist
        return False
    entries = result_dict['result']['entry']
    # If only one static route exists, the library returns a dict. If multiples exist, it returns a list.
    if isinstance(entries, palo_helpers.XmlDictConfig):
        entries = [result_dict['result']['entry']]  # put the single entry dict into a list
    # Now we can safely iterate over a list of entries, even if we only got one
    for entry in entries:
        logger.debug(f"ENTRY: {entry}")
        if destination == entry['destination']:
            # found a route with the same destination
            logger.debug(f"Found static route with existing destination. route name: {entry['name']}")
            return entry['name']
    logger.debug(f"Did not find static route with destination: {destination}. Returning False")
    return False


def set_static_route(hostname, api_key, destination, next_hop, interface, virtual_router='default') -> Optional[str]:
    """
    Set Static Route
    :param string hostname: the IP or hostname for the palo management interface
    :param string api_key: the api key to access the palo (from palo_helpers.getApiKey)
    :param string destination: the cidr block of the route (ex. 10.0.0.0/8)
    :param string next_hop: the IP address of the next hop (ex 10.250.1.1)
    :param string interface: the name of the palo network interface (ex ethernet1/2)
    :param string virtual_router: the name of the palo virtual router (default: "default")
    :return: string route_name if matching route exists, else false
    """
    logger.debug(
        f"Setting static route on host: {hostname} virtual_router: {virtual_router} destination: {destination}, "
        f"next_hop: {next_hop}, interface: {interface}")

    static_route_xpath = f"/config/devices/entry[@name='localhost.localdomain']/network/virtual-router/" \
        f"entry[@name='{virtual_router}']/routing-table/ip/static-route"

    # See if an identical route already exists
    route_name = get_matching_route_name(hostname=hostname, api_key=api_key, destination=destination, next_hop=next_hop,
                                         virtual_router=virtual_router, interface=interface)
    if route_name:
        # route already exists, exit with route name
        logger.warning(f"Identical route {route_name} already exists. Doing nothing and returning route_name")
        return route_name

    # See if a route with this destination already exists
    route_name = static_route_exists(hostname=hostname, api_key=api_key,
                                     destination=destination, virtual_router=virtual_router)
    if route_name:
        # found a route with the same destination, update it with interface and next_hop
        logger.info(f"Found static route with existing destination. route name: {route_name}")
        logger.info(f"Updating Route: {route_name} with next_hop: {next_hop}, interface: {interface}")
        xpath = f"{static_route_xpath}/entry[@name='{route_name}']"
        element = f"<nexthop><ip-address>{next_hop}</ip-address></nexthop> " \
            f"<nexthop><ip-address>{next_hop}</ip-address> </nexthop> "
        result_xml = palo_helpers.panSetConfig(hostname, api_key, xpath, element)
        result_dict = palo_helpers.XmlDictConfig(ET.XML(result_xml))
        # if result_dict['response']['status'] == 'success':
        if result_dict['status'] == 'success':
            logger.info(f"successfully updated static route {route_name}. Returning route_name")
        else:
            logger.error(f"failed to update static route: {route_name}. Returning error")
            logger.error(f"{result_dict}")
            return False
    else:
        # We need to create a route
        # Generate a nifty route name (cant have / in route name)
        route_name = destination.replace("/", '-')
        logger.info(f"No existing route with this destination: {destination} exists. Creating new route: {route_name}")
        xpath = f"{static_route_xpath}"
        element = f"<entry name='{route_name}'>" \
            f"<path-monitor>" \
            f"  <enable>no</enable><failure-condition>any</failure-condition><hold-time>2</hold-time>" \
            f"</path-monitor> " \
            f"<nexthop><ip-address>{next_hop}</ip-address></nexthop> " \
            f"<bfd><profile>None</profile></bfd> " \
            f"<interface>ethernet1/2</interface> " \
            f"<metric>10</metric> " \
            f"<destination>{destination}</destination> " \
            f"<route-table><unicast/></route-table> " \
            f"</entry>"
        result_xml = palo_helpers.panSetConfig(hostname, api_key, xpath, element)
        result_dict = palo_helpers.XmlDictConfig(ET.XML(result_xml))
        if result_dict['status'] == 'success':
            logger.info(f"successfully created static route. Returning route_name {route_name}")
        else:
            logger.error(f"Failed to update static route: {route_name}. Returning False")
            logger.error(f"{result_dict}")
            logger.debug(f"XPATH: {xpath}")
            logger.debug(f"ELEMENT: {element}")
            return False

    # Commit the change
    if palo_helpers.commit(hostname=hostname, api_key=api_key, message=f"created static route {route_name}"):
        return route_name
    else:
        return False


def delete_static_route(hostname, api_key, destination, virtual_router='default') -> Optional[str]:
    """
    Deletes a route from a palo alto virtual router with a given destination
    :param string hostname: IP or hostname of the palo management interface
    :param string api_key: API key for connecting to palo (as created by palo_helpers.getApiKey())
    :param string destination: the destination cidr that we want to delete (ex 10.250.0.0/16)
    :param string virtual_router: Name of the palo virtual router (default: default)
    :return: Returns deleted route name if successful, else False
    """

    static_route_xpath = f"/config/devices/entry[@name='localhost.localdomain']/network/virtual-router/" \
        f"entry[@name='{virtual_router}']/routing-table/ip/static-route"

    # See if the route even exists
    route_name = static_route_exists(hostname=hostname, api_key=api_key,
                                     destination=destination, virtual_router=virtual_router)
    if not route_name:
        logging.warning(f"Did not find route with matching destination: {destination} "
                        f"on virtual router: {virtual_router}. Doing nothing & returning True")
        return True

    # If we are still here, the route exists, lets delete it
    logger.info(f"Deleting route: {route_name} from virtual router: {virtual_router}")
    xpath = f"{static_route_xpath}/entry[@name='{route_name}']"
    result_xml = palo_helpers.panDelConfig(hostname=hostname, api_key=api_key, xpath=xpath)
    result_dict = palo_helpers.XmlDictConfig(ET.XML(result_xml))
    if result_dict['status'] == 'success':
        logger.info(f"successfully deleted static route: {route_name}")
    else:
        logger.error(f"Failed to delete static route: {route_name}. Returning False")
        logger.error(f"{result_dict}")
        logger.debug(f"XPATH: {xpath}")
        return False

    # Commit the change
    if palo_helpers.commit(hostname=hostname, api_key=api_key, message=f"deleted static route {route_name}"):
        return route_name
    else:
        return False


@helper.create
def create(event, context):
    logger.info("Got Create")
    palo_user = event['ResourceProperties']['PaloUser']
    palo_password = event['ResourceProperties']['PaloPassword']
    palo_mgt_ip = event['ResourceProperties']['PaloMgtIp']
    next_hop_ip = event['ResourceProperties']['NextHopIp']
    destination_cidr_block = event['ResourceProperties']['DestinationCidrBlock']
    interface = event['ResourceProperties']['Interface']
    virtual_router = event['ResourceProperties']['VirtualRouter']

    try:
        api_key = palo_helpers.getApiKey(hostname=palo_mgt_ip, username=palo_user, password=palo_password)
    except Exception as e:
        logging.error(f"unable to connect to {palo_mgt_ip} as user: {palo_user} with password: {palo_password}")
        logging.error(e)
        return False

    set_static_route(hostname=palo_mgt_ip, api_key=api_key, destination=destination_cidr_block,
                     next_hop=next_hop_ip, virtual_router=virtual_router, interface=interface)


@helper.update
def update(event, context):
    logger.info("Got Update")
    # Update is the same as create, just pass the event and context to that function
    create(event, context)


@helper.delete
def delete(event, context):
    logger.info("Got Delete")
    palo_user = event['ResourceProperties']['PaloUser']
    palo_password = event['ResourceProperties']['PaloPassword']
    palo_mgt_ip = event['ResourceProperties']['PaloMgtIp']
    destination_cidr_block = event['ResourceProperties']['DestinationCidrBlock']
    virtual_router = event['ResourceProperties']['VirtualRouter']

    try:
        api_key = palo_helpers.getApiKey(hostname=palo_mgt_ip, username=palo_user, password=palo_password)
    except Exception as e:
        logging.error(f"unable to connect to {palo_mgt_ip} as user: {palo_user} with password: {palo_password}")
        logging.error(e)
        return False

    delete_static_route(hostname=palo_mgt_ip, api_key=api_key, destination=destination_cidr_block,
                        virtual_router=virtual_router)


def handler(event, context):
    helper(event, context)
