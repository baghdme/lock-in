import requests
import json

BASE_URL = "http://localhost:5000"

def test_parse_schedule():
    test_text = "I have an exam on Thursday at 5pm, and I also have 2 meetings one on Monday at 3pm and another on Wednesday at 6:15PM"
    
    response = requests.post(
        f"{BASE_URL}/parse-schedule",
        json={"text": test_text}
    )
    
    print("Parse Schedule Response:")
    print(json.dumps(response.json(), indent=2))
    return response.json()

def test_get_schedule():
    response = requests.get(f"{BASE_URL}/get-schedule")
    
    print("\nGet Schedule Response:")
    print(json.dumps(response.json(), indent=2))
    return response.json()

def test_modify_schedule():
    # First get the current schedule
    current_schedule = test_get_schedule()
    
    # Modify request
    modification_request = "Change the Monday meeting to 4pm"
    
    response = requests.post(
        f"{BASE_URL}/modify-schedule",
        json={"text": modification_request}
    )
    
    print("\nModify Schedule Response:")
    print(json.dumps(response.json(), indent=2))
    return response.json()

def test_health():
    response = requests.get(f"{BASE_URL}/health")
    
    print("\nHealth Check Response:")
    print(json.dumps(response.json(), indent=2))
    return response.json()

if __name__ == "__main__":
    # Test all endpoints
    test_parse_schedule()
    test_get_schedule()
    test_modify_schedule()
    test_health() 