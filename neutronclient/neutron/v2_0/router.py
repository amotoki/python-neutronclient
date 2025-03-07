# Copyright 2012 OpenStack Foundation.
# All Rights Reserved
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

from __future__ import print_function

import argparse

from oslo_serialization import jsonutils

from neutronclient._i18n import _
from neutronclient.common import exceptions
from neutronclient.common import utils
from neutronclient.neutron import v2_0 as neutronV20
from neutronclient.neutron.v2_0 import availability_zone


def _format_external_gateway_info(router):
    try:
        return jsonutils.dumps(router['external_gateway_info'])
    except (TypeError, KeyError):
        return ''


class ListRouter(neutronV20.ListCommand):
    """List routers that belong to a given tenant."""

    resource = 'router'
    _formatters = {'external_gateway_info': _format_external_gateway_info, }
    list_columns = ['id', 'name', 'external_gateway_info', 'distributed', 'ha']
    pagination_support = True
    sorting_support = True


class ShowRouter(neutronV20.ShowCommand):
    """Show information of a given router."""

    resource = 'router'


class CreateRouter(neutronV20.CreateCommand):
    """Create a router for a given tenant."""

    resource = 'router'
    _formatters = {'external_gateway_info': _format_external_gateway_info, }

    def add_known_arguments(self, parser):
        parser.add_argument(
            '--admin-state-down',
            dest='admin_state', action='store_false',
            help=_('Set admin state up to false.'))
        parser.add_argument(
            '--admin_state_down',
            dest='admin_state', action='store_false',
            help=argparse.SUPPRESS)
        parser.add_argument(
            'name', metavar='NAME',
            help=_('Name of router to create.'))
        utils.add_boolean_argument(
            parser, '--distributed', dest='distributed',
            help=_('Create a distributed router.'))
        utils.add_boolean_argument(
            parser, '--ha', dest='ha',
            help=_('Create a highly available router.'))

        availability_zone.add_az_hint_argument(parser, self.resource)

    def args2body(self, parsed_args):
        body = {'admin_state_up': parsed_args.admin_state}
        neutronV20.update_dict(parsed_args, body,
                               ['name', 'tenant_id', 'distributed', 'ha'])
        availability_zone.args2body_az_hint(parsed_args, body)
        return {self.resource: body}


class DeleteRouter(neutronV20.DeleteCommand):
    """Delete a given router."""

    resource = 'router'


class UpdateRouter(neutronV20.UpdateCommand):
    """Update router's information."""

    resource = 'router'

    def add_known_arguments(self, parser):
        parser.add_argument(
            '--name',
            help=_('Name of this router.'))
        utils.add_boolean_argument(
            parser, '--admin-state-up', dest='admin_state',
            help=_('Specify the administrative state of the router'
                   ' (True meaning "Up")'))
        utils.add_boolean_argument(
            parser, '--admin_state_up', dest='admin_state',
            help=argparse.SUPPRESS)
        utils.add_boolean_argument(
            parser, '--distributed', dest='distributed',
            help=_('True means this router should operate in'
                   ' distributed mode.'))
        routes_group = parser.add_mutually_exclusive_group()
        routes_group.add_argument(
            '--route', metavar='destination=CIDR,nexthop=IP_ADDR',
            action='append', dest='routes',
            type=utils.str2dict_type(required_keys=['destination', 'nexthop']),
            help=_('Route to associate with the router.'
                   ' You can repeat this option.'))
        routes_group.add_argument(
            '--no-routes',
            action='store_true',
            help=_('Remove routes associated with the router.'))

    def args2body(self, parsed_args):
        body = {}
        if hasattr(parsed_args, 'admin_state'):
            body['admin_state_up'] = parsed_args.admin_state
        neutronV20.update_dict(parsed_args, body,
                               ['name', 'distributed'])
        if parsed_args.no_routes:
            body['routes'] = None
        elif parsed_args.routes:
            body['routes'] = parsed_args.routes
        return {self.resource: body}


class RouterInterfaceCommand(neutronV20.NeutronCommand):
    """Based class to Add/Remove router interface."""

    resource = 'router'

    def call_api(self, neutron_client, router_id, body):
        raise NotImplementedError()

    def success_message(self, router_id, portinfo):
        raise NotImplementedError()

    def get_parser(self, prog_name):
        parser = super(RouterInterfaceCommand, self).get_parser(prog_name)
        parser.add_argument(
            'router', metavar='ROUTER',
            help=_('ID or name of the router.'))
        parser.add_argument(
            'interface', metavar='INTERFACE',
            help=_('The format is "SUBNET|subnet=SUBNET|port=PORT". '
                   'Either a subnet or port must be specified. '
                   'Both ID and name are accepted as SUBNET or PORT. '
                   'Note that "subnet=" can be omitted when specifying a '
                   'subnet.'))
        return parser

    def run(self, parsed_args):
        self.log.debug('run(%s)' % parsed_args)
        neutron_client = self.get_client()

        if '=' in parsed_args.interface:
            resource, value = parsed_args.interface.split('=', 1)
            if resource not in ['subnet', 'port']:
                exceptions.CommandError(_('You must specify either subnet or '
                                        'port for INTERFACE parameter.'))
        else:
            resource = 'subnet'
            value = parsed_args.interface

        _router_id = neutronV20.find_resourceid_by_name_or_id(
            neutron_client, self.resource, parsed_args.router)

        _interface_id = neutronV20.find_resourceid_by_name_or_id(
            neutron_client, resource, value)
        body = {'%s_id' % resource: _interface_id}

        portinfo = self.call_api(neutron_client, _router_id, body)
        print(self.success_message(parsed_args.router, portinfo),
              file=self.app.stdout)


class AddInterfaceRouter(RouterInterfaceCommand):
    """Add an internal network interface to a router."""

    def call_api(self, neutron_client, router_id, body):
        return neutron_client.add_interface_router(router_id, body)

    def success_message(self, router_id, portinfo):
        return (_('Added interface %(port)s to router %(router)s.') %
                {'router': router_id, 'port': portinfo['port_id']})


class RemoveInterfaceRouter(RouterInterfaceCommand):
    """Remove an internal network interface from a router."""

    def call_api(self, neutron_client, router_id, body):
        return neutron_client.remove_interface_router(router_id, body)

    def success_message(self, router_id, portinfo):
        # portinfo is not used since it is None for router-interface-delete.
        return _('Removed interface from router %s.') % router_id


class SetGatewayRouter(neutronV20.NeutronCommand):
    """Set the external network gateway for a router."""

    resource = 'router'

    def get_parser(self, prog_name):
        parser = super(SetGatewayRouter, self).get_parser(prog_name)
        parser.add_argument(
            'router', metavar='ROUTER',
            help=_('ID or name of the router.'))
        parser.add_argument(
            'external_network', metavar='EXTERNAL-NETWORK',
            help=_('ID or name of the external network for the gateway.'))
        parser.add_argument(
            '--disable-snat', action='store_true',
            help=_('Disable source NAT on the router gateway.'))
        parser.add_argument(
            '--fixed-ip', metavar='subnet_id=SUBNET,ip_address=IP_ADDR',
            action='append',
            type=utils.str2dict_type(optional_keys=['subnet_id',
                                                    'ip_address']),
            help=_('Desired IP and/or subnet on external network: '
                   'subnet_id=<name_or_id>,ip_address=<ip>. '
                   'You can specify both of subnet_id and ip_address or '
                   'specify one of them as well. '
                   'You can repeat this option.'))
        return parser

    def run(self, parsed_args):
        self.log.debug('run(%s)' % parsed_args)
        neutron_client = self.get_client()
        _router_id = neutronV20.find_resourceid_by_name_or_id(
            neutron_client, self.resource, parsed_args.router)
        _ext_net_id = neutronV20.find_resourceid_by_name_or_id(
            neutron_client, 'network', parsed_args.external_network)
        router_dict = {'network_id': _ext_net_id}
        if parsed_args.disable_snat:
            router_dict['enable_snat'] = False
        if parsed_args.fixed_ip:
            ips = []
            for ip_spec in parsed_args.fixed_ip:
                subnet_name_id = ip_spec.get('subnet_id')
                if subnet_name_id:
                    subnet_id = neutronV20.find_resourceid_by_name_or_id(
                        neutron_client, 'subnet', subnet_name_id)
                    ip_spec['subnet_id'] = subnet_id
                ips.append(ip_spec)
            router_dict['external_fixed_ips'] = ips
        neutron_client.add_gateway_router(_router_id, router_dict)
        print(_('Set gateway for router %s') % parsed_args.router,
              file=self.app.stdout)


class RemoveGatewayRouter(neutronV20.NeutronCommand):
    """Remove an external network gateway from a router."""

    resource = 'router'

    def get_parser(self, prog_name):
        parser = super(RemoveGatewayRouter, self).get_parser(prog_name)
        parser.add_argument(
            'router', metavar='ROUTER',
            help=_('ID or name of the router.'))
        return parser

    def run(self, parsed_args):
        self.log.debug('run(%s)' % parsed_args)
        neutron_client = self.get_client()
        _router_id = neutronV20.find_resourceid_by_name_or_id(
            neutron_client, self.resource, parsed_args.router)
        neutron_client.remove_gateway_router(_router_id)
        print(_('Removed gateway from router %s') % parsed_args.router,
              file=self.app.stdout)
