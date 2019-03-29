# Palo configuration


#### Zones

* `dmz` zone - connection to internet
* `trusted` zone - connections to corporate and internal vpcs
* `web` zone - connections to web facing vpcs

#### Interfaces

* `mgt-if` - eth0, dhcp, in trusted subnet
* `ethernet1/1` - eth1, dhcp w/ default route added to `default` v-router, `dmz` zone, `default` v-router
* `ethernet1/2` - eth2, dhcp, `trusted` zone, `default` v-router
* `ethernet1/3` - eth3, dhcp, `web` zone, `default` v-router

#### Virtual Router
* `default` virtual router
    * default route: 0.0.0.0/0 to ethernet 1/1 (added via dhcp)
    * Static routes:
        * `10-net` - 10.0.0.0/8 route to ethernet1/2
        * `172-net` - 172.16.0.0/12 route to ethernet1/2
        * `192-net` - 192.168.0.0/16 route to ethernet1/2
        
    *Note*: any web vpc cidrs must be added and send to ethernet1/3 interface

#### Security Policies
* `trusted-to-any` - allows src: `trusted` to dest: ALL
* `web-to-dmz`- allows src: `web` to dest: `dmz`
* `dmz-to-web` - allows src: `dmz` to dest: `web`
* `intrazone-default` - allows all intra-zone traffic (default rule)
* `interzone-default` - denies all inter-zone traffic (default rule)

    *Note*: Any inbound web > trusted traffic must be specifically authorized with a new rule

#### Nat Policies
* `nat-trusted-to-dmz-all` - SNAT all outbound traffic from src: `trusted` to dest `dmz`
* `nat-web-to-dmz-https` - SNAT outbound https traffic from src: `web` to dest `dmz`
* `nat-web-to-dmz-http` - SNAT outbound http traffic from src: `web` to dest `dmz`

#### VPN Crypto Profiles
* `aws-vpn-ike-crypto-profile` sha1, aes-128-cbc, group2, 3600 secs
* `aws-vpn-ipsec-crypto-profile` sha1, aes-128-cbc, group2, 28800 secs

#### Other
* VM Series Cloudwatch Monitoring - enabled