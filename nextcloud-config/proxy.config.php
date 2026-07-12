<?php
$CONFIG = array(
  'trusted_proxies' => array(
    0 => '172.16.0.0/12',
    1 => '192.168.0.0/16',
    2 => '100.64.0.0/10',
  ),
  'overwriteprotocol' => 'https',
  'forwarded_for_headers' => array('HTTP_X_FORWARDED_FOR'),
  'default_phone_region' => 'IN',
);
