import requests
import json
from pprint import pprint

def test_parser(text, case_name):
    print(f"\n{'='*80}\nTest Case {case_name}:")
    print(f"Input: {text}\n")
    
    response = requests.post(
        "http://localhost:5000/parse-tasks",
        json={"text": text},
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        result = response.json()
        print("Parsed Output:")
        pprint(result, indent=2)
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
    
    print('='*80)
    return response.json() if response.status_code == 200 else None

# Test cases
test_cases = [
    # Case 1: Mixed academic and personal tasks with priorities
    ("i need to finish EECE503 homework asap, then clean my room. also have to email professor about the midterm grade by tomorrow. oh and don't forget to buy groceries from the store!", 
     "Mixed Academic and Personal Tasks"),
    
    # Case 2: Multiple meetings and deadlines
    ("meeting with team at 2pm to discuss project progress. then have another meeting at 4pm for CMPS252 group work. need to prepare slides before the first meeting. important: send agenda to everyone by 1pm.",
     "Multiple Meetings and Deadlines"),
    
    # Case 3: Unstructured daily tasks
    ("gotta do laundry sometime today... also need to call mom, maybe around 6pm? should probably clean the kitchen too, it's getting messy. and pick up that package from the post office before it closes!",
     "Unstructured Daily Tasks"),
    
    # Case 4: Course-related tasks with implicit deadlines
    ("review PHYS201 notes before class tomorrow. submit lab report by end of day. also need to finish the programming assignment... oh and schedule a meeting with the TA to discuss the project.",
     "Course Tasks with Deadlines"),
    
    # Case 5: Priority mixing with regular tasks
    ("urgent: fix the bug in the code! also need to update documentation when done. after that grab lunch with the team to discuss next steps. critical: push changes before 3pm standup meeting.",
     "Priority Mixed Tasks"),
    
    # Case 6: Shopping and errands
    ("need to buy: milk, eggs, bread from the store. also pick up prescription from pharmacy. then get new notebooks for class, and maybe grab coffee on the way back. don't forget to get cash from the atm!",
     "Shopping and Errands"),
    
    # Case 7: Mixed formal and casual language
    ("gotta finish that important presentation for tomorrow's meeting... also need to review EECE350 materials. should probably organize my desk at some point lol. and don't forget about the team sync at 3!",
     "Mixed Formal and Casual"),
    
    # Case 8: Time-sensitive tasks
    ("submit report by 5pm sharp! then head to the group meeting at 6pm. need to prepare the demo before that... and send updates to the team by eod. maybe grab dinner after everything's done.",
     "Time-sensitive Tasks"),
    
    # Case 9: Multiple course codes and priorities
    ("finish CMPS252 assignment first, it's super urgent! then review EECE503 slides for tomorrow's quiz. after that, maybe look at MATH201 homework if there's time. important: email PHYS201 professor about missed class.",
     "Multiple Courses"),
    
    # Case 10: Complex mixed tasks
    ("need to: clean apartment (urgent!), buy groceries for dinner party, finish coding project by 8pm, call mom sometime today, prepare for tomorrow's presentation, and don't forget team meeting at 3pm to discuss progress!",
     "Complex Mixed Tasks")
]

if __name__ == "__main__":
    print("Starting parser tests...")
    results = []
    
    for text, case_name in test_cases:
        result = test_parser(text, case_name)
        if result:
            results.append(result)
    
    # Summary
    print("\nTest Summary:")
    print(f"Total test cases: {len(test_cases)}")
    print(f"Successful parses: {len(results)}")
    
    # Task and Meeting Statistics
    total_tasks = sum(len(r['tasks']) for r in results)
    total_meetings = sum(len(r['meetings']) for r in results)
    total_course_codes = sum(len(r['course_codes']) for r in results)
    
    print(f"\nTotal tasks detected: {total_tasks}")
    print(f"Total meetings detected: {total_meetings}")
    print(f"Total course codes detected: {total_course_codes}") 