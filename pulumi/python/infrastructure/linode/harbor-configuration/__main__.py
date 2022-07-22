import base64
import json
import urllib.request
import urllib.error
import os
import time
from typing import List

import pulumi
from kic_util import pulumi_config

stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
pulumi_user = pulumi_config.get_pulumi_user()


def project_name_from_harbor_dir():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', 'harbor')
    return pulumi_config.get_pulumi_project_name(project_path)


harbor_project_name = project_name_from_harbor_dir()
stack_ref_id = f"{pulumi_user}/{harbor_project_name}/{stack_name}"
stack_ref = pulumi.StackReference(stack_ref_id)
harbor_hostname_output = stack_ref.require_output('harbor_hostname')
harbor_user_output = stack_ref.require_output('harbor_user')
harbor_password_output = stack_ref.require_output('harbor_password')


def configure_harbor(params: List[str]) -> bool:
    hostname = params[0]
    user = params[1]
    password = params[2]
    base_url = f'https://{hostname}/api/v2.0'
    base64creds = str(base64.b64encode(f'{user}:{password}'.encode('ascii')), 'ascii')
    max_retries = 12
    retries = 0
    timeout = 1000

    def is_harbor_is_up() -> bool:
        url = f'{base_url}/health'
        request = urllib.request.Request(url=url, method='GET')
        request.add_header(key='Authorization', val=f'Basic {base64creds}')

        try:
            with urllib.request.urlopen(url=request, timeout=timeout) as context:
                if context.getcode() != 200:
                    return False

                health_check = json.load(context)
                components = health_check['components']
                for component in components:
                    if component['status'] != 'healthy':
                        pulumi.log.info(f"Harbor component [{component['name']}] is not healthy")
                        return False

                return True
        except urllib.error.URLError as e:
            # Don't retry for name resolution failures
            if e.errno == -3:
                raise e

            pulumi.log.info(f'Unable to connect to Harbor [try {retries+1} of {max_retries}]: {e}')
            return False

    def modify_default_project_registry():
        url = f'{base_url}/projects/library/metadatas/public'
        request = urllib.request.Request(url=url, method='PUT')
        request.add_header(key='Authorization', val=f'Basic {base64creds}')
        request.add_header(key='Content-Type', val='application/json')
        body = {
            'public': 'false'
        }
        body_json = json.dumps(body)
        request.data = body_json.encode('utf-8')
        urllib.request.urlopen(url=request, timeout=timeout)

    while not is_harbor_is_up():
        retries += 1
        timeout = 1000 * retries
        time.sleep(timeout)

        if retries >= max_retries:
            raise f'Harbor has not come up after {retries} retries'

    pulumi.log.info('Harbor is up, modifying default registry')
    modify_default_project_registry()

    return True


harbor_is_alive = pulumi.Output.all(harbor_hostname_output, harbor_user_output, harbor_password_output)\
    .apply(configure_harbor)

pulumi.export('harbor_is_alive', harbor_is_alive)
