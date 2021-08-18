#!/usr/bin/env python3

import requests
import sys
import json

stdin_json = json.load(sys.stdin)
if 'application_url' not in stdin_json:
    raise ValueError("Missing expected key 'application_url' in STDIN json data")

url = f"{stdin_json['application_url']}/login"

payload = 'username=testuser&password=password'
headers = {
  'Content-Type': 'application/x-www-form-urlencoded'
}

response = requests.request("POST", url, headers=headers, data=payload, verify=False)
response_code = response.status_code

if response_code != 200:
    print(f'Application failed health check [url={url},response_code={response_code}', file=sys.stderr)
    sys.exit(1)
else:
    print('Application passed health check', file=sys.stderr)
    print(stdin_json['application_url'])
