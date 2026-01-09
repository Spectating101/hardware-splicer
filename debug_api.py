#!/usr/bin/env python3
import sys
sys.path.insert(0, 'src')

from api_server import app
import json

client = app.test_client()

# Test learning paths
print("Testing GET /api/learning-paths")
try:
    response = client.get('/api/learning-paths')
    print(f"Status: {response.status_code}")
    if response.status_code != 200:
        print(f"Error: {response.data.decode()[:500]}")
    else:
        data = json.loads(response.data)
        print(f"Success: {data.get('count')} paths")
except Exception as e:
    print(f"Exception: {e}")
    import traceback
    traceback.print_exc()

print()

# Test specific path
print("Testing GET /api/learning-paths/arduino_basics")
try:
    response = client.get('/api/learning-paths/arduino_basics')
    print(f"Status: {response.status_code}")
    if response.status_code != 200:
        print(f"Error: {response.data.decode()[:500]}")
    else:
        data = json.loads(response.data)
        print(f"Success: {data.get('name')}")
except Exception as e:
    print(f"Exception: {e}")
    import traceback
    traceback.print_exc()

print()

# Test build instructions list
print("Testing GET /api/instructions")
try:
    response = client.get('/api/instructions')
    print(f"Status: {response.status_code}")
    if response.status_code != 200:
        print(f"Error: {response.data.decode()[:500]}")
    else:
        data = json.loads(response.data)
        print(f"Success: {data.get('count')} projects")
except Exception as e:
    print(f"Exception: {e}")
    import traceback
    traceback.print_exc()
