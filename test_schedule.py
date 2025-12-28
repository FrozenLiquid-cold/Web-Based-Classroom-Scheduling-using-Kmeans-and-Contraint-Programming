#!/usr/bin/env python3
"""Test script to trigger scheduling and check results"""

import requests
import json
import time

# API base URL
BASE_URL = "http://127.0.0.1:8000"

def test_schedule():
    """Trigger a schedule request and monitor progress"""
    
    # Schedule request payload
    payload = {
        "course_id": 3,  # Based on logs, course 3 was being scheduled
        "year": 1,
        "semester": 1,
        "blocks_count": 1
    }
    
    print("Sending schedule request...")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    # Send schedule request
    response = requests.post(f"{BASE_URL}/api/schedule/course", json=payload)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return
    
    result = response.json()
    job_id = result.get("job_id")
    
    if not job_id:
        print("No job_id in response")
        print(result)
        return
    
    print(f"Job started with ID: {job_id}")
    
    # Monitor job status
    while True:
        status_response = requests.get(f"{BASE_URL}/api/schedule/status?job_id={job_id}")
        
        if status_response.status_code != 200:
            print(f"Status check error: {status_response.status_code}")
            break
        
        status = status_response.json()
        print(f"Status: {status}")
        
        if status.get("status") in ["completed", "failed"]:
            break
        
        time.sleep(2)
    
    # Get final results if completed
    if status.get("status") == "completed":
        result_id = status.get("result_id")
        if result_id:
            result_response = requests.get(f"{BASE_URL}/api/schedule/result/{result_id}")
            if result_response.status_code == 200:
                result_data = result_response.json()
                print("\nFinal schedule results:")
                print(json.dumps(result_data, indent=2))
            else:
                print(f"Error getting results: {result_response.status_code}")

if __name__ == "__main__":
    test_schedule()
