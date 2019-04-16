# palo_static_route.py
"""
This lambda manages service in a palo alto firewall
"""

# Initialise the aws cfn helper, all inputs are optional, this example shows the defaults
from crhelper import CfnResource
helper = CfnResource(json_logging=False, log_level='DEBUG', boto_level='CRITICAL')

try:
    # Init code goes here where exceptions can be caught and cfn notified
    import ipaddress
    import moo_helpers
    import palo_helpers
    import xml.etree.ElementTree as ET
    from typing import Union

    logger = moo_helpers.get_console_logger()
    # logger.setLevel('DEBUG')
    import logging

except Exception as e:
    helper.init_failure(e)


def service_exists(hostname, api_key, service_name, vsys_name='vsys1') -> bool:
    """
    Determines if a service with a given name exists
    :param string hostname: hostname of the router
    :param string api_key: api key to access router
    :param string service_name: name of the service to search for
    :param string vsys_name: name of the vsys (default='vsys1')
    :return: True if exists, else false
    """
    logger.debug(f"Looking for service on palo: {service_name}, vsys_name: {vsys_name} service_name: {service_name}")
    if service_name in ['service-http', 'service-https']:
        logger.debug(f"service name {service_name} is in redefined services list. Returning True")
        return True
    if not palo_helpers.vsys_exists(hostname=hostname, api_key=api_key, vsys_name=vsys_name):
        return False
    xpath = f"/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='{vsys_name}']" \
        f"/service/entry[@name='{service_name}']"
    response = palo_helpers.panGetConfig(hostname=hostname, api_key=api_key, xpath=xpath)
    if palo_helpers.XmlDictConfig(ET.XML(response))['result']:
        return True
    logging.debug(f"service_name: {service_name} does not exist on vsys: {vsys_name} host: {hostname}. Returning False")
    return False


def set_service(hostname, api_key, service_name, destination_ports, protocol='tcp', service_description='',
                vsys_name='vsys1') -> Union[str, bool]:
    """
    Creates or updates a service
    :param string hostname: hostname of the router
    :param string api_key: api key to access the router
    :param string service_name: the service name (up to 63 characters).
    :param string destination_ports: the destination port number (0 to 65535) or range of port numbers (80-83)
                                     used by the service. Multiple ports or ranges must be separated by commas.
    :param string protocol: the protocol used by the service [tcp|udp|stcp] (default = 'tcp')
    :param string service_description: a description for the service (up to 1023 characters). (default = '')
    :param string vsys_name: name of the vsys to use. Default = vsys1
    :return: string service_name if successful, else False
    """

    # Some sanity checking
    if len(service_name) > 63:
        logger.warning(f"service name: {service_name} is {len(service_name)} chars long. Max is 63. Returning False")
        return False
    if len(service_description) > 1023:
        logger.warning(f"service: {service_name}, description: {service_description} is {len(service_name)} chars long."
                       f" Max is 1023. Returning False")
        return False
    if protocol.lower() not in ['tcp', 'udp', 'stcp']:
        logger.warning(f"service:{service_name}, protocol: {protocol.lower()} is not tcp, udp or stcp. Returning False")
        return False

    xpath = f"/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='{vsys_name}']" \
        f"/service"

    element = f"<entry name='{service_name}'> " \
        f"<protocol>" \
        f"  <{protocol.lower()}>" \
        f"      <port>{destination_ports}</port>" \
        f"      <override> <no/> </override>" \
        f"  </{protocol.lower()}>" \
        f"</protocol>" \
        f"<description>{service_description}</description>" \
        f"</entry>"

    config_action = "create"
    if service_exists(hostname=hostname, api_key=api_key, vsys_name=vsys_name, service_name=service_name):
        config_action = "update"
    logger.info(f"{config_action} service {service_name}")

    result_xml = palo_helpers.panSetConfig(hostname, api_key, xpath, element)
    result_dict = palo_helpers.XmlDictConfig(ET.XML(result_xml))
    if result_dict['status'] == 'success':
        logger.info(f"Succeeded in {config_action}ing service: {service_name}")
    else:
        logger.error(f"Failed to {config_action} service: {service_name}. Returning False")
        logger.error(f"{result_dict}")
        logger.debug(f"XPATH: {xpath}")
        logger.debug(f"ELEMENT: {element}")
        return False

    if palo_helpers.commit(hostname=hostname, api_key=api_key,
                               message=f"{config_action} service {service_name}"):
        return service_name
    return False


def delete_service(hostname, api_key, service_name, vsys_name='vsys1') -> Union[str, bool]:
    """
    Deletes a service from a palo alto virtual router with a given name
    :param string hostname: IP or hostname of the palo management interface
    :param string api_key: API key for connecting to palo (as created by palo_helpers.getApiKey())
    :param string service_name: the name of the seervice to delete
    :param string vsys_name: name of the virtual system
    :return: string service_name if successful, else False
    """

    # See if the rule even exists
    if not service_exists(hostname=hostname, api_key=api_key, service_name=service_name, vsys_name=vsys_name):
        logging.warning(f"Did not find service: {service_name} on host: {hostname}, vsys: {vsys_name}. "
                        f"Doing nothing & returning True")
        return True

    xpath = f"/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='{vsys_name}']" \
        f"/service/entry[@name='{service_name}']"

    # If we are still here, the service exists, lets delete it
    logger.info(f"Deleting service: {service_name} from host: {hostname} vsys: {vsys_name}")
    result_xml = palo_helpers.panDelConfig(hostname=hostname, api_key=api_key, xpath=xpath)
    result_dict = palo_helpers.XmlDictConfig(ET.XML(result_xml))
    if result_dict['status'] == 'success':
        logger.info(f"successfully deleted service : {service_name}")
    else:
        logger.error(f"Failed to delete service: {service_name}. Returning False")
        logger.error(f"{result_dict}")
        logger.debug(f"XPATH: {xpath}")
        return False

    # Commit the change
    if palo_helpers.commit(hostname=hostname, api_key=api_key, message=f"deleted service {service_name}"):
        return service_name
    return False


@helper.create
def create(event, context):
    logger.info("Got Create")
    palo_user = event['ResourceProperties']['PaloUser']
    palo_password = event['ResourceProperties']['PaloPassword']
    palo_mgt_ip = event['ResourceProperties']['PaloMgtIp']
    vsys_name = event['ResourceProperties']['VsysName']

    service_name = event['ResourceProperties']['ServiceName']
    service_description = event['ResourceProperties']['ServiceDescription']
    destination_ports = event['ResourceProperties']['DestinationPorts']
    protocol = event['ResourceProperties']['Protocol']

    try:
        api_key = palo_helpers.getApiKey(hostname=palo_mgt_ip, username=palo_user, password=palo_password)
    except Exception as e:
        logging.error(f"unable to connect to {palo_mgt_ip} as user: {palo_user} with password: {palo_password}")
        logging.error(e)
        return False

    return set_service(hostname=palo_mgt_ip, api_key=api_key, vsys_name=vsys_name,
                       service_name=service_name, service_description=service_description,
                       protocol=protocol, destination_ports=destination_ports)


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
    vsys_name = event['ResourceProperties']['VsysName']
    service_name = event['ResourceProperties']['ServiceName']

    try:
        api_key = palo_helpers.getApiKey(hostname=palo_mgt_ip, username=palo_user, password=palo_password)
    except Exception as e:
        logging.error(f"unable to connect to {palo_mgt_ip} as user: {palo_user} with password: {palo_password}")
        logging.error(e)
        return False

    return delete_service(hostname=palo_mgt_ip, api_key=api_key, vsys_name=vsys_name,
                          service_name=service_name)


def handler(event, context):
    helper(event, context)

