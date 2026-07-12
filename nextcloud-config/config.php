<?php

/*
 * WARNING
 *
 * This file gets modified by automatic processes and all lines that are not
 * active code (ie. comments) are lost during that process.
 *
 * If you want to document things with comments or use constants add your settings
 * in a '<NAME>.config.php' file which will be included and rendered into this file.
 *
 * Example:
 *   <?php
 *   $CONFIG = [];
 *
 * See also: https://docs.nextcloud.com/server/latest/admin_manual/configuration_server/config_sample_php_parameters.html#multiple-merged-configuration-files
 */
$CONFIG = array (
  'htaccess.RewriteBase' => '/',
  'memcache.local' => '\\OC\\Memcache\\APCu',
  'apps_paths' => 
  array (
    0 => 
    array (
      'path' => '/var/www/html/apps',
      'url' => '/apps',
      'writable' => false,
    ),
    1 => 
    array (
      'path' => '/var/www/html/custom_apps',
      'url' => '/custom_apps',
      'writable' => true,
    ),
  ),
  'upgrade.disable-web' => true,
  'instanceid' => 'oc8bcipn8o6m',
  'passwordsalt' => 'tHrCX/tKbnMtKSKmcJLclwOnbqrsas',
  'secret' => 'BXLrumcjvNRqBIzUMFVaaOOl4pdng57+SiwqCEWOyP9jy4DQ',
  'trusted_domains' => 
  array (
    0 => '192.168.1.4',
    1 => 'localhost',
    2 => '100.94.81.46',
  ),
  'datadirectory' => '/var/www/html/data',
  'dbtype' => 'mysql',
  'version' => '34.0.1.2',
  'overwrite.cli.url' => 'https://100.94.81.46',
  'overwriteprotocol' => 'https',
  'dbname' => 'nextcloud',
  'dbhost' => 'nextcloud-db',
  'dbtableprefix' => 'oc_',
  'mysql.utf8mb4' => true,
  'dbuser' => 'nextcloud',
  'dbpassword' => 'K31P0wulZfI9OZ1cdWkTxyOP',
  'installed' => true,
  'trusted_proxies' => 
  array (
    0 => '172.16.0.0/12',
    1 => '192.168.0.0/16',
    2 => '100.64.0.0/10',
  ),
  'forwarded_for_headers' => 
  array (
    0 => 'HTTP_X_FORWARDED_FOR',
  ),
  'default_phone_region' => 'IN',
  'allow_local_remote_servers' => false,
);
