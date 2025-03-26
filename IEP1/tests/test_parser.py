import unittest
import sys
import os
import json
from typing import Dict, List

# Add the parent directory to the Python path so we can import the parser
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from parser import parse_with_llm

class TestParser(unittest.TestCase):
    def setUp(self):
        """Set up test cases with known inputs and expected outputs"""
        self.test_cases = [
            # Test Case 1: Tasks with dependencies and meetings
            {
                "input": "Today: First need to review EECE503 slides (30 mins) before lab report (2 hours, high priority!!!). Then check EECE503N project emails (15 mins). Meeting with prof in EEB 228 @ 2:30pm (1 hour).",
                "expected": {
                    "tasks": [
                        {
                            "description": "review EECE503 slides",
                            "priority": "medium",
                            "time": None,
                            "duration_minutes": 30,
                            "category": "Tutorial",
                            "is_fixed_time": False,
                            "location": None,
                            "prerequisites": [],
                            "course_code": "EECE503"
                        },
                        {
                            "description": "finish EECE503 lab report",
                            "priority": "high",
                            "time": None,
                            "duration_minutes": 120,
                            "category": "Lab Work",
                            "is_fixed_time": False,
                            "location": None,
                            "prerequisites": ["review EECE503 slides"],
                            "course_code": "EECE503"
                        },
                        {
                            "description": "check EECE503N project emails",
                            "priority": "medium",
                            "time": None,
                            "duration_minutes": 15,
                            "category": "Admin",
                            "is_fixed_time": False,
                            "location": None,
                            "prerequisites": [],
                            "course_code": "EECE503N"
                        }
                    ],
                    "meetings": [
                        {
                            "description": "meeting with prof",
                            "priority": "medium",
                            "time": "2:30pm",
                            "duration_minutes": 60,
                            "location": "EEB 228",
                            "preparation_tasks": [],
                            "course_code": None
                        }
                    ],
                    "course_codes": ["EECE503", "EECE503N"]
                }
            },
            # Test Case 2: Fixed-time tasks and meetings with some unspecified durations
            {
                "input": "EECE210 schedule today: Must grade assignments 9-10:30am in office, then prepare tutorial materials. Lab setup for EECE503 experiment needs 45 mins, must be done before 2pm lab.",
                "expected": {
                    "tasks": [
                        {
                            "description": "grade assignments",
                            "priority": "medium",
                            "time": "9:00am",
                            "duration_minutes": 90,  # Calculated from 9-10:30am
                            "category": "Grading",
                            "is_fixed_time": True,
                            "location": "office",
                            "prerequisites": [],
                            "course_code": "EECE210"
                        },
                        {
                            "description": "prepare tutorial materials",
                            "priority": "medium",
                            "time": None,
                            "duration_minutes": None,  # Not specified
                            "category": "Tutorial",
                            "is_fixed_time": False,
                            "location": None,
                            "prerequisites": [],
                            "course_code": "EECE210"
                        },
                        {
                            "description": "lab setup for EECE503 experiment",
                            "priority": "high",
                            "time": None,
                            "duration_minutes": 45,
                            "category": "Lab Work",
                            "is_fixed_time": False,
                            "location": None,
                            "prerequisites": [],
                            "course_code": "EECE503"
                        }
                    ],
                    "meetings": [],
                    "course_codes": ["EECE210", "EECE503"]
                }
            },
            # Test Case 3: Mixed tasks with explicit and implicit durations
            {
                "input": """EECE503N schedule for today:
                1. Team meeting in Bliss 205 @ 3pm (1 hour)
                2. Must finish assignment before meeting (2 hours, high priority)
                3. Review lecture slides
                4. Optional: Lab demo if time permits""",
                "expected": {
                    "tasks": [
                        {
                            "description": "finish EECE503N assignment",
                            "priority": "high",
                            "time": None,
                            "duration_minutes": 120,
                            "category": "Assignment",
                            "is_fixed_time": False,
                            "location": None,
                            "prerequisites": [],
                            "course_code": "EECE503N"
                        },
                        {
                            "description": "review lecture slides",
                            "priority": "medium",
                            "time": None,
                            "duration_minutes": None,
                            "category": "Tutorial",
                            "is_fixed_time": False,
                            "location": None,
                            "prerequisites": [],
                            "course_code": "EECE503N"
                        },
                        {
                            "description": "lab demo",
                            "priority": "low",
                            "time": None,
                            "duration_minutes": None,
                            "category": "Lab Work",
                            "is_fixed_time": False,
                            "location": None,
                            "prerequisites": [],
                            "course_code": "EECE503N"
                        }
                    ],
                    "meetings": [
                        {
                            "description": "team meeting",
                            "priority": "high",
                            "time": "3:00pm",
                            "duration_minutes": 60,
                            "location": "Bliss 205",
                            "preparation_tasks": [],
                            "course_code": "EECE503N"
                        }
                    ],
                    "course_codes": ["EECE503N"]
                }
            }
        ]

    def test_output_structure(self):
        """Test that the parser output has the correct structure"""
        for test_case in self.test_cases:
            result = parse_with_llm(test_case["input"])
            
            # Check basic structure
            self.assertIn("tasks", result)
            self.assertIn("meetings", result)
            self.assertIn("course_codes", result)
            self.assertIn("topics", result)
            
            # Check tasks structure
            for task in result["tasks"]:
                self.assertIn("description", task)
                self.assertIn("priority", task)
                self.assertIn("time", task)
                self.assertIn("duration_minutes", task)
                self.assertIn("category", task)
                self.assertIn("is_fixed_time", task)
                self.assertIn("location", task)
                self.assertIn("prerequisites", task)
                self.assertIn("course_code", task)
                
            # Check meetings structure
            for meeting in result["meetings"]:
                self.assertIn("description", meeting)
                self.assertIn("priority", meeting)
                self.assertIn("time", meeting)
                self.assertIn("duration_minutes", meeting)
                self.assertIn("location", meeting)
                self.assertIn("preparation_tasks", meeting)
                self.assertIn("course_code", meeting)

    def test_course_code_extraction(self):
        """Test that course codes are correctly extracted"""
        for test_case in self.test_cases:
            result = parse_with_llm(test_case["input"])
            expected_codes = test_case["expected"]["course_codes"]
            actual_codes = [c.upper() for c in result["course_codes"]]
            
            # Check if all expected codes are found (handling both full and shortened versions)
            for code in expected_codes:
                code = code.upper()
                found = False
                for actual in actual_codes:
                    # Check if either the exact code matches or if it's a part of a full code
                    if code == actual or (code in actual and actual.endswith(code)):
                        found = True
                        break
                self.assertTrue(found, f"Expected code {code} not found in {actual_codes}")

    def test_priority_assignment(self):
        """Test that priorities are correctly assigned"""
        for test_case in self.test_cases:
            result = parse_with_llm(test_case["input"])
            
            # Check tasks priorities
            for task in result["tasks"]:
                self.assertIn(task["priority"].lower(), ["high", "medium", "low"])
                
            # Check meetings priorities
            for meeting in result["meetings"]:
                self.assertIn(meeting["priority"].lower(), ["high", "medium", "low"])

    def test_category_assignment(self):
        """Test that task categories are correctly assigned"""
        valid_categories = [
            "Lab Work",      # Lab-related tasks and experiments
            "Assignment",    # Homework and submissions
            "Tutorial",      # Teaching and preparation
            "Admin",        # Administrative tasks
            "Grading",      # Grading and assessment
            "Meeting",      # Meeting-related tasks
            "Preparation"   # Preparation for other tasks
        ]
        for test_case in self.test_cases:
            result = parse_with_llm(test_case["input"])
            for task in result["tasks"]:
                self.assertIn(task["category"], valid_categories, 
                    f"Invalid category '{task['category']}' for task: {task['description']}")

    def calculate_accuracy(self, expected, actual):
        """Calculate accuracy score for a test case"""
        score = 0
        total_points = 0
        
        # Course code matching (1 point each)
        expected_codes = set(c.upper() for c in expected["course_codes"])
        actual_codes = set(c.upper() for c in actual["course_codes"])
        code_matches = len(expected_codes.intersection(actual_codes))
        score += code_matches
        total_points += len(expected_codes)
        
        # Task matching (5 points each: description, priority, category, duration if specified, prerequisites)
        for exp_task in expected["tasks"]:
            points_for_task = 4  # Base points without duration
            if exp_task["duration_minutes"] is not None:
                points_for_task += 1  # Add point for duration if specified
            total_points += points_for_task
            
            for act_task in actual["tasks"]:
                if exp_task["description"].lower() in act_task["description"].lower():
                    score += 1  # Description match
                    if exp_task["priority"] == act_task["priority"]:
                        score += 1  # Priority match
                    if exp_task["category"] == act_task["category"]:
                        score += 1  # Category match
                    if exp_task["duration_minutes"] is not None:
                        if act_task["duration_minutes"] is not None and \
                           abs(exp_task["duration_minutes"] - act_task["duration_minutes"]) <= 15:
                            score += 1  # Duration match (within 15 minutes)
                    if set(exp_task["prerequisites"]) == set(act_task["prerequisites"]):
                        score += 1  # Prerequisites match
                    break
        
        # Meeting matching (4 points each: description, time, location, duration if specified)
        for exp_meeting in expected["meetings"]:
            points_for_meeting = 3  # Base points without duration
            if exp_meeting["duration_minutes"] is not None:
                points_for_meeting += 1  # Add point for duration if specified
            total_points += points_for_meeting
            
            for act_meeting in actual["meetings"]:
                if exp_meeting["description"].lower() in act_meeting["description"].lower():
                    score += 1  # Description match
                    if exp_meeting["time"] == act_meeting["time"]:
                        score += 1  # Time match
                    if exp_meeting["location"] == act_meeting["location"]:
                        score += 1  # Location match
                    if exp_meeting["duration_minutes"] is not None:
                        if act_meeting["duration_minutes"] is not None and \
                           abs(exp_meeting["duration_minutes"] - act_meeting["duration_minutes"]) <= 15:
                            score += 1  # Duration match (within 15 minutes)
                    break
        
        return (score / total_points * 100) if total_points > 0 else 0

    def test_accuracy(self):
        """Test overall accuracy of the parser"""
        accuracies = []
        for test_case in self.test_cases:
            result = parse_with_llm(test_case["input"])
            accuracy = self.calculate_accuracy(test_case["expected"], result)
            accuracies.append(accuracy)
            print(f"\nTest case: {test_case['input'][:50]}...")
            print(f"Accuracy: {accuracy:.2f}%")
        
        avg_accuracy = sum(accuracies) / len(accuracies)
        print(f"\nAverage accuracy: {avg_accuracy:.2f}%")
        self.assertGreaterEqual(avg_accuracy, 70, "Average accuracy should be at least 70%")

if __name__ == '__main__':
    unittest.main()
