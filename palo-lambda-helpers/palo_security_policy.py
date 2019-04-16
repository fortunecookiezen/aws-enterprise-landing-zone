# palo_static_route.py
"""
This lambda manages security policies in a palo alto firewall
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
    from palo_service import service_exists

    logger = moo_helpers.get_console_logger()
    # logger.setLevel('DEBUG')
    import logging

except Exception as e:
    helper.init_failure(e)


def security_rule_exists(hostname, api_key, rule_name, vsys_name='vsys1') -> bool:
    """
    Test to see if a security policy with a specific name exists
    :param string hostname: the IP or hostname for the palo management interface
    :param string api_key: the api key to access the palo (from palo_helpers.getApiKey)
    :param string rule_name: the name of the firewall rule
    :param string vsys_name: the name of the virtual system on the firewall (default: 'vsys1')
    :return: True if matching security_policy exists, else False
    """
    logger.debug(f"Looking for security rule on palo: {hostname}, vsys_name: {vsys_name} rule_name: {rule_name}")
    if not palo_helpers.vsys_exists(hostname=hostname, api_key=api_key, vsys_name=vsys_name):
        return False
    xpath = f"/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='{vsys_name}']" \
        f"/rulebase/security/rules/entry[@name='{rule_name}']"
    response = palo_helpers.panGetConfig(hostname=hostname, api_key=api_key, xpath=xpath)
    if palo_helpers.XmlDictConfig(ET.XML(response))['result']:
        return True
    logging.debug(f"rule_name: {rule_name} does not exist on vsys: {vsys_name} host: {hostname}. Returning False")
    return False


def security_zone_exists(hostname, api_key, zone_name, vsys_name='vsys1') -> bool:
    """
    Determines if security zone exists
    :param string hostname: hostname of the router
    :param string api_key: api key to access router
    :param string zone_name: name of the zone to search
    :param string vsys_name: name of the vsys (default=vsys1)
    :return: True if zone exists, else False
    """
    logger.debug(f"Looking for security zone on palo: {hostname}, vsys_name: {vsys_name} zone_name: {zone_name}")
    if not palo_helpers.vsys_exists(hostname=hostname, api_key=api_key, vsys_name=vsys_name):
        return False
    xpath = f"/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='{vsys_name}']" \
            f"/zone/entry[@name='{zone_name}']"
    response = palo_helpers.panGetConfig(hostname=hostname, api_key=api_key, xpath=xpath)
    if palo_helpers.XmlDictConfig(ET.XML(response))['result']:
        return True
    logging.debug(f"zone_name: {zone_name} does not exist on vsys: {vsys_name} host: {hostname}. Returning False")
    return False


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


def cidr_isvalid(cidr) -> bool:
    """
    Determines if a cidr is a valid IP or CIDR range
    :param string cidr: the IP or cidr to check
    :return: True if valid, else False
    """
    try:
        ipaddress.ip_address(cidr)
    except ValueError as ip_error:
        try:
            ipaddress.ip_network(cidr)
        except ValueError as net_error:
            logging.debug(ip_error)
            logging.debug(net_error)
            logger.debug(f"cidr {cidr} not valid ip or network address. returning False")
            return False
    return True


def set_security_rule(hostname, api_key, rule_name, rule_description='',
                      source_zones=None, source_cidrs=None,
                      destination_zones=None, destination_cidrs=None,
                      applications=None, services=None, users=None,
                      action='allow', vsys_name='vsys1') -> Union[str, bool]:
    """
    Set Security Rule
    :param string hostname: the IP or hostname for the palo management interface
    :param string api_key: the api key to access the palo (from palo_helpers.getApiKey)
    :param string rule_name: the name of the rule to manage <63 chars
    :param string rule_description: the description of the rule to manage <1024 chars. (default: '')
    :param list source_zones: the name of the source security zone (default = ['any'])
    :param list source_cidrs: list of cidrs allowed to send traffic (default = ['any'])
    :param list destination_zones: list of allowed security zones for destination (default = ['any'])
    :param list destination_cidrs: list of cidrs allowed to receive traffic (default = ['any']
    :param list applications: list of allowed applications (default = ['any'])
    :param list services: list of allowed services (default = ['any'])
    :param list users: list of allowed users (default = ['any'])
    :param string action: firewall rule [allow|deny]. (default = 'allow')
    :param string vsys_name: the name of the vsys (default: vsys1)
    :return: string rule_name if successful, else False
    """
    logger.debug(
        f"Setting security rule on host: {hostname} vsys: {vsys_name} action: {action}"
        f"source_cidrs: {source_cidrs} source_zones: {source_zones}"
        f"destination_cidrs: {destination_cidrs} destination_zones: {destination_zones}, "
        f"applications: {applications}"
    )

    # make sure rule_name is < 64 chars
    if len(rule_name) >= 63:
        logger.critical(f"rule_name {rule_name} has {len(rule_name)} chars. Must be > 64. Returning False")
        return False

    # make sure rule_description < 1024 chars
    if len(rule_description) >= 1023:
        logger.critical(f"rule_description {rule_description} has {len(rule_description)} chars."
                        f"Must be > 1024. Returning False")
        return False

    # make sure action is valid
    if action not in ['allow', 'deny']:
        logger.critical(f"action: {action} must be either 'allow' or 'deny'. Returning False")
        return False

    # source cidrs xml element
    source_cidrs = ['any'] if not source_cidrs else source_cidrs
    source_cidrs_element = str()
    for source_cidr in source_cidrs:
        if source_cidr == 'any' or cidr_isvalid(source_cidr):
            source_cidrs_element += f"<member>{source_cidr}</member>"
        else:
            logging.critical(f"source cidr: {source_cidr} does not appear to be valid. Returning False")
            return False

    # source zones xml element
    source_zones = ['any'] if not source_zones else source_zones
    source_zones_element = str()
    for source_zone in source_zones:
        if source_zone == 'any' or security_zone_exists(hostname=hostname, api_key=api_key, vsys_name=vsys_name,
                                                        zone_name=source_zone):
            source_zones_element += f"<member>{source_zone}</member>"
        else:
            logging.critical(f"source zone: {source_zone} does not appear to be valid. Returning False")
            return False

    # destination cidrs xml element
    destination_cidrs = ['any'] if not destination_cidrs else destination_cidrs
    destination_cidrs_element = str()
    for destination_cidr in destination_cidrs:
        if destination_cidr == 'any' or cidr_isvalid(destination_cidr):
            destination_cidrs_element += f"<member>{destination_cidr}</member>"
        else:
            logging.critical(f"destination cidr: {destination_cidr} does not appear to be valid. Returning False")
            return False

    # destination zones xml element
    destination_zones = ['any'] if not destination_zones else destination_zones
    destination_zones_element = str()
    for destination_zone in destination_zones:
        if destination_zone == 'any' or security_zone_exists(hostname=hostname, api_key=api_key, vsys_name=vsys_name,
                                                             zone_name=destination_zone):
            destination_zones_element += f"<member>{destination_zone}</member>"
        else:
            logging.critical(f"destination zone: {destination_zone} does not appear to be valid. Returning False")
            return False

    # users xml element
    users = ['any'] if not users else users
    users_element = str()
    for user in users:
        # TODO: check that the user is valid
        users_element += f"<member>{user}</member>"

    # applications xml element
    applications_element = "<application>"
    applications = [] if not applications else applications
    for application in applications:
        # TODO: check that the application name is valid
        applications_element += f"<member>{application}</member>"
    applications_element += "</application>"

    # services xml element
    services_element = str()
    services = ['application-default'] if not services else services
    for service in services:
        if service == 'application-default' or service_exists(hostname=hostname, api_key=api_key,
                                                              service_name=service, vsys_name=vsys_name):
            services_element += f"<member>{service}</member>"
        else:
            logging.critical(f"service: {service} doesnt exist on host: {hostname}, vsys: {vsys_name}"
                             f"Returning False")
            return False

    xpath = f"/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='{vsys_name}']" \
        f"/rulebase/security/rules"

    element = f"<entry name='{rule_name}'> " \
        f"<description>{rule_description}</description> " \
        f"<from>{destination_zones_element}</from> " \
        f"<to>{source_zones_element}</to> " \
        f"<destination>{destination_cidrs_element}</destination> " \
        f"<service>{services_element}</service> " \
        f"<source>{source_cidrs_element}</source> " \
        f"<action>{action}</action> " \
        f"<category><member>any</member></category> " \
        f"<hip-profiles><member>any</member></hip-profiles> " \
        f"{applications_element} " \
        f"<source-user>{users_element}</source-user> " \
        f"<action>{action}</action> "\
        f"</entry>"

    config_action = "create"
    if security_rule_exists(hostname=hostname, api_key=api_key, rule_name=rule_name, vsys_name=vsys_name):
        config_action = "update"
    logger.info(f"{config_action} rule {rule_name}")

    result_xml = palo_helpers.panSetConfig(hostname, api_key, xpath, element)
    result_dict = palo_helpers.XmlDictConfig(ET.XML(result_xml))
    if result_dict['status'] == 'success':
        logger.info(f"Succeeded in {config_action}ing rule: {rule_name}")
    else:
        logger.error(f"Failed to {config_action} rule: {rule_name}. Returning False")
        logger.error(f"{result_dict}")
        logger.debug(f"XPATH: {xpath}")
        logger.debug(f"ELEMENT: {element}")
        return False

    # Commit the change
    if palo_helpers.commit(hostname=hostname, api_key=api_key, message=f"{config_action} security rule {rule_name}"):
        return rule_name
    return False


def delete_security_rule(hostname, api_key, rule_name, vsys_name='vsys1') -> Union[str, bool]:
    """
    Deletes a rule from a palo alto virtual router with a given name
    :param string hostname: IP or hostname of the palo management interface
    :param string api_key: API key for connecting to palo (as created by palo_helpers.getApiKey())
    :param string rule_name: the name of the security rule to delete
    :param string vsys_name: name of the virtual system
    :return: string deleted rule_name if successful, else False
    """

    # See if the rule even exists
    if not security_rule_exists(hostname=hostname, api_key=api_key, vsys_name=vsys_name, rule_name=rule_name):
        logging.warning(f"Did not find security rule: {rule_name} on host: {hostname}, vsys: {vsys_name}. "
                        f"Doing nothing & returning True")
        return True

    xpath = f"/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='{vsys_name}']" \
        f"/rulebase/security/rules/entry[@name='{rule_name}']"

    # If we are still here, the rule exists, lets delete it
    logger.info(f"Deleting rule: {rule_name} from host: {hostname} vsys: {vsys_name}")
    result_xml = palo_helpers.panDelConfig(hostname=hostname, api_key=api_key, xpath=xpath)
    result_dict = palo_helpers.XmlDictConfig(ET.XML(result_xml))
    if result_dict['status'] == 'success':
        logger.info(f"successfully deleted security rule: {rule_name}")
    else:
        logger.error(f"Failed to delete security rule: {rule_name}. Returning False")
        logger.error(f"{result_dict}")
        logger.debug(f"XPATH: {xpath}")
        return False

    if palo_helpers.commit(hostname=hostname, api_key=api_key, message=f"delete security rule {rule_name}"):
        return rule_name
    return False


@helper.create
def create(event, context) -> Union[str, bool]:
    """
    Creates a security rule
    :param event:
    :param context:
    :return: string rule name if successful, else False
    """

    logger.info("Got Create")
    palo_user = event['ResourceProperties']['PaloUser']
    palo_password = event['ResourceProperties']['PaloPassword']
    palo_mgt_ip = event['ResourceProperties']['PaloMgtIp']
    vsys_name = event['ResourceProperties']['VsysName']

    rule_name = event['ResourceProperties']['RuleName']
    rule_description = event['ResourceProperties']['RuleDescription']
    source_cidrs = event['ResourceProperties']['SourceCidrs']
    source_zones = event['ResourceProperties']['SourceZones']
    destination_cidrs = event['ResourceProperties']['DestinationCidrs']
    destination_zones = event['ResourceProperties']['DestinationZones']
    applications = event['ResourceProperties']['Applications']
    services = event['ResourceProperties']['Services']
    users = event['ResourceProperties']['Users']

    try:
        api_key = palo_helpers.getApiKey(hostname=palo_mgt_ip, username=palo_user, password=palo_password)
    except Exception as e:
        logging.error(f"unable to connect to {palo_mgt_ip} as user: {palo_user} with password: {palo_password}")
        logging.error(e)
        return False

    return set_security_rule(hostname=palo_mgt_ip, api_key=api_key, vsys_name=vsys_name,
                             rule_name=rule_name, rule_description=rule_description,
                             source_zones=source_zones, source_cidrs=source_cidrs,
                             destination_zones=destination_zones, destination_cidrs=destination_cidrs,
                             applications=applications, services=services, users=users)


@helper.update
def update(event, context) -> Union[str, bool]:
    """
    Updates a security rule
    :param event:
    :param context:
    :return: string rule name if successful, else False
    """
    logger.info("Got Update")
    # Update is the same as create, just pass the event and context to that function
    return create(event, context)


@helper.delete
def delete(event, context) -> Union[str, bool]:
    """
    Deletes a security rule
    :param event:
    :param context:
    :return: string rule name if successful, else False
    """
    logger.info("Got Delete")
    palo_user = event['ResourceProperties']['PaloUser']
    palo_password = event['ResourceProperties']['PaloPassword']
    palo_mgt_ip = event['ResourceProperties']['PaloMgtIp']
    vsys_name = event['ResourceProperties']['VsysName']

    rule_name = event['ResourceProperties']['RuleName']

    try:
        api_key = palo_helpers.getApiKey(hostname=palo_mgt_ip, username=palo_user, password=palo_password)
    except Exception as e:
        logging.error(f"unable to connect to {palo_mgt_ip} as user: {palo_user} with password: {palo_password}")
        logging.error(e)
        return False

    return delete_security_rule(hostname=palo_mgt_ip, api_key=api_key, vsys_name=vsys_name,
                                rule_name=rule_name)


def handler(event, context):
    helper(event, context)

