import unittest
import palo_security_policy
import palo_service
import palo_static_route
import palo_helpers as palo_helpers
import moo_helpers as moo_helpers
import os


class TestPaloHelpers(unittest.TestCase):

    def setUp(self):
        self.logger = moo_helpers.get_console_logger()
        self.logger.setLevel('DEBUG')
        # Requires that the local port 443 is forwarded to palo management interface 443
        self.hostname = 'localhost'
        self.username = 'admin'
        self.password = os.environ['PALO_PASSWORD']
        self.api_key = palo_helpers.getApiKey(hostname=self.hostname,
                                              username=self.username,
                                              password=self.password)
        self.vsys_name = 'vsys1'
        self.existing_service_name = 'service-http'
        self.existing_rule_name = 'trusted-to-any'

        self.test_service_name = 'test-service'
        self.test_service_description = 'test service description'
        self.test_service_protocol = 'tcp'
        self.test_service_destination_ports = '80,443,1024-8080'

        self.test_rule_name = 'test_rule'
        self.source_cidrs = ["10.250.1.0/24", '10.250.1.1']
        self.source_zones = ["trusted", "dmz"]
        self.destination_cidrs = ["10.251.1.0/24", "10.252.1.1"]
        self.destination_zones = ["web", "dmz"]

        self.virtual_router = 'default'
        self.existing_route_name = '10-net'
        self.existing_route_name = '10.0.0.0-8'
        self.existing_route_destination = '10.0.0.0/8'
        self.existing_route_next_hop = '10.250.1.1'
        self.existing_route_interface = 'ethernet1/2'

        self.test_route_destination = '192.168.1.0/24'
        self.test_route_next_hop = '192.168.1.1'
        self.test_route_interface = 'ethernet1/1'
        self.test_route_name = self.test_route_destination.replace("/", "-")

    def test_get_api_key(self):
        api_key = self.api_key = palo_helpers.getApiKey(
            hostname=self.hostname,
            username=self.username,
            password=self.password
        )
        self.assertIsInstance(api_key, str)

        try:
            api_key = self.api_key = palo_helpers.getApiKey(
                hostname=self.hostname,
                username=self.username,
                password='badpass'
            )
        except:
            api_key = False
        self.assertFalse(api_key)

    def test_get_matching_route_name(self):
        result = palo_static_route.get_matching_route_name(
            hostname=self.hostname, api_key=self.api_key,
            virtual_router=self.virtual_router,
            destination=self.existing_route_destination,
            next_hop=self.existing_route_next_hop,
            interface=self.existing_route_interface,
            )
        # if route 10-net route exist, uncomment the following
        self.assertEqual(self.existing_route_name, result)
        #self.assertFalse(result)

    def test_static_route_exists(self):
        # palo_static_route.static_route_exists(hostname, api_key, destination, virtual_router='default'):
        result = palo_static_route.static_route_exists(
            hostname=self.hostname, api_key=self.api_key,
            virtual_router=self.virtual_router,
            destination=self.existing_route_destination
        )
        # if route 10-net route doesnt exist, uncomment the following
        self.assertTrue(result)
        #self.assertFalse(result)

    def test_set_delete_static_route(self):
        result = palo_static_route.set_static_route(
            hostname=self.hostname, api_key=self.api_key,
            virtual_router=self.virtual_router,
            destination=self.test_route_destination,
            next_hop=self.test_route_next_hop,
            interface=self.test_route_interface,
        )
        self.assertEqual(self.test_route_name, result)

        result = palo_static_route.static_route_exists(
            hostname=self.hostname, api_key=self.api_key,
            virtual_router=self.virtual_router,
            destination=self.test_route_destination
        )
        self.assertEqual(self.test_route_name, result)

        result = palo_static_route.delete_static_route(
            hostname=self.hostname, api_key=self.api_key,
            virtual_router=self.virtual_router,
            destination=self.test_route_destination
        )
        self.assertEqual(self.test_route_name, result)

    def test_vsys_exists(self):
        result = palo_helpers.vsys_exists(
            hostname=self.hostname,
            api_key=self.api_key,
            vsys_name=self.vsys_name
        )
        self.assertTrue(result)
        result = palo_helpers.vsys_exists(
            hostname=self.hostname,
            api_key=self.api_key,
            vsys_name='invalid_vsys'
        )
        self.assertFalse(result)

    def test_security_rule_exists(self):
        result = palo_security_policy.security_rule_exists(
            hostname=self.hostname,
            api_key=self.api_key,
            rule_name=self.existing_rule_name,
            vsys_name=self.vsys_name,
        )
        self.assertTrue(result)

        result = palo_security_policy.security_rule_exists(
            hostname=self.hostname,
            api_key=self.api_key,
            rule_name='fake_rule_name',
            vsys_name=self.vsys_name,
        )
        self.assertFalse(result)

    def test_security_zone_exists(self):
        result = palo_security_policy.security_zone_exists(
            hostname=self.hostname,
            api_key=self.api_key,
            zone_name=self.source_zones[0],
            vsys_name=self.vsys_name,
        )
        self.assertTrue(result)

        result = palo_security_policy.security_zone_exists(
            hostname=self.hostname,
            api_key=self.api_key,
            zone_name='fake_zone_name',
            vsys_name=self.vsys_name,
        )
        self.assertFalse(result)

    def test_cidr_isvalid(self):
        for cidr in self.source_cidrs:
            result = palo_security_policy.cidr_isvalid(cidr)
            self.assertTrue(result)
        result = palo_security_policy.cidr_isvalid('invalid_cidr')
        self.assertFalse(result)

    def test_service_exists(self):
        result = palo_service.service_exists(
            hostname=self.hostname,
            api_key=self.api_key,
            service_name=self.existing_service_name,
            vsys_name=self.vsys_name,
        )
        self.assertTrue(result)

        result = palo_service.service_exists(
            hostname=self.hostname,
            api_key=self.api_key,
            service_name='fake_service_name',
            vsys_name=self.vsys_name,
        )
        self.assertFalse(result)

    def test_set_delete_service(self):
        result = palo_service.set_service(
            hostname=self.hostname,
            api_key=self.api_key,
            service_name=self.test_service_name,
            service_description=self.test_service_description,
            protocol=self.test_service_protocol,
            destination_ports=self.test_service_destination_ports,
            vsys_name=self.vsys_name,
        )
        self.assertEqual(self.test_service_name, result)

        result = palo_service.service_exists(
            hostname=self.hostname,
            api_key=self.api_key,
            service_name=self.test_service_name,
            vsys_name=self.vsys_name,
        )
        self.assertTrue(result)
        result = palo_service.delete_service(
            hostname=self.hostname,
            api_key=self.api_key,
            service_name=self.test_service_name,
            vsys_name=self.vsys_name,
        )
        self.assertEqual(self.test_service_name, result)

    def test_set_delete_security_rule(self):
        result = palo_security_policy.set_security_rule(
            hostname=self.hostname,
            api_key=self.api_key,
            rule_name=self.test_rule_name,
            source_zones=self.source_zones,
            source_cidrs=self.source_cidrs,
            destination_zones=self.destination_zones,
            destination_cidrs=self.destination_cidrs,
            applications=None,
            services=[self.existing_service_name],
            users=None,
            action='allow',
            vsys_name='vsys1'
        )
        self.assertEqual(self.test_rule_name, result)

        result = palo_security_policy.security_rule_exists(
            hostname=self.hostname,
            api_key=self.api_key,
            rule_name=self.test_rule_name,
            vsys_name=self.vsys_name,
        )
        self.assertTrue(result)

        result = palo_security_policy.set_security_rule(
            hostname=self.hostname,
            api_key=self.api_key,
            rule_name=self.test_rule_name,
            vsys_name='vsys1'
        )
        self.assertEqual(self.test_rule_name, result)

