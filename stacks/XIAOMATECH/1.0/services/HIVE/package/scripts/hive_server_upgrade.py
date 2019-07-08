"""
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

"""

# Python Imports
import os
import re

# Ambari Commons & Resource Management Imports
from resource_management.core import shell
from resource_management.core.exceptions import Fail
from resource_management.core.logger import Logger
from resource_management.core.resources.system import Execute
from resource_management.libraries.functions import format

def deregister():
    """
  Runs the "hive --service hiveserver2 --deregister <version>" command to
  de-provision the server in preparation for an upgrade. This will contact
  ZooKeeper to remove the server so that clients that attempt to connect
  will be directed to other servers automatically. Once all
  clients have drained, the server will shutdown automatically.

  However, since Ambari does not support Hive Server rolling upgrades due to the port change
  affecting Hive Clients not using the ZK discovery service, the daemon might be forcefully
  killed before it has been deregistered and drained.

  This function will obtain the Kerberos ticket if security is enabled.
  :return:
  """
    import params

    Logger.info(
        'HiveServer2 executing "deregister" command to complete upgrade...')

    if params.security_enabled:
        kinit_command = format(
            "{kinit_path_local} -kt {smoke_user_keytab} {smokeuser_principal}; "
        )
        Execute(kinit_command, user=params.smokeuser)

    # calculate the current hive server version
    current_hiveserver_version = _get_current_hiveserver_version()
    if current_hiveserver_version is None:
        raise Fail(
            'Unable to determine the current HiveServer2 version to deregister.'
        )

    hive_server_conf_dir = params.hive_server_conf_dir
    if not os.path.exists(hive_server_conf_dir):
        hive_server_conf_dir = "/etc/hive"

    # deregister
    hive_execute_path = params.execute_path
    hive_execute_path = _get_hive_execute_path()

    command = format(
        params.install_dir +
        'hive --config {hive_server_conf_dir} --service hiveserver2 --deregister '
        + current_hiveserver_version)
    Execute(command, user=params.hive_user, path=hive_execute_path, tries=1)


def _get_hive_execute_path():
    """
  Returns the exact execute path to use for the given stack-version.
  This method does not return the "current" path
  :return: Hive execute path for the exact stack-version
  """
    import params

    hive_execute_path = params.execute_path
    return hive_execute_path


def _get_current_hiveserver_version():
    """
  Runs "hive --version" and parses the result in order
  to obtain the current version of hive.

  :return:  the hiveserver2 version, returned by "hive --version"
  """
    import params

    try:
        hive_execute_path = _get_hive_execute_path()
        version_hive_bin = params.hive_bin
        command = format('{version_hive_bin}/hive --version')
        return_code, output = shell.call(
            command, user=params.hive_user, path=hive_execute_path)
    except Exception, e:
        Logger.error(str(e))
        raise Fail(
            'Unable to execute hive --version command to retrieve the hiveserver2 version.'
        )

    if return_code != 0:
        raise Fail(
            'Unable to determine the current HiveServer2 version because of a non-zero return code of {0}'
            .format(str(return_code)))

    match = re.search('^(Hive) ([0-9]+.[0-9]+.\S+)', output, re.MULTILINE)

    if match:
        current_hive_server_version = match.group(2)
        return current_hive_server_version
    else:
        raise Fail(
            'The extracted hiveserver2 version "{0}" does not matching any known pattern'
            .format(output))
