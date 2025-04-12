# EEP2: Course Buddy Service

## Overview

The Course Buddy is a specialized component of our scheduling system that enhances learning efficiency by analyzing course materials and adjusting preparation time based on student knowledge. It works by creating a personalized tab for each course in the user's schedule, allowing material uploads, knowledge assessment, and intelligent preparation time adjustments.

## Key Features

1. **Course-Specific Workspaces** - Each course from the schedule gets its own dedicated tab
2. **Material Analysis** - Upload and process course documents (slides, notes, etc.)
3. **Knowledge Assessment** - Take diagnostic quizzes generated from your materials
4. **Adaptive Time Planning** - Receive intelligent suggestions to adjust preparation time
5. **Content Summarization** - Get concise summaries of course content
6. **Interactive Q&A** - Ask questions about the material with contextual awareness

## Architecture

The Course Buddy follows a microservice architecture with a clear separation of concerns:

```
┌───────────────────┐     ┌───────────────────┐
│                   │     │                   │
│   UI Service      │◄────►    EEP2 Service   │
│   (Frontend)      │     │  (Course Buddy)   │
│                   │     │                   │
└───────────────────┘     └─────────┬─────────┘
                                    │
                                    ▼
                          ┌───────────────────┐
                          │   Business Logic  │
                          │                   │
                          │ ┌───────────────┐ │
                          │ │ Document      │ │
                          │ │ Processing    │ │
                          │ └───────────────┘ │
                          │                   │
                          │ ┌───────────────┐ │
                          │ │ Quiz          │ │
                          │ │ Generation    │ │
                          │ └───────────────┘ │
                          │                   │
                          │ ┌───────────────┐ │
                          │ │ Time          │ │
                          │ │ Adjustment    │ │
                          │ └───────────────┘ │
                          │                   │
                          └────┬──────┬──────┘
                               │      │
                 ┌─────────────┘      └────────────┐
                 ▼                                  ▼
      ┌─────────────────────┐            ┌─────────────────────┐
      │      IEP-LLM        │            │   IEP-Summarizer    │
      │  (Internal Endpoint)│            │  (Internal Endpoint)│
      └──────────┬──────────┘            └──────────┬──────────┘
                 │                                   │
                 ▼                                   ▼
      ┌─────────────────────┐            ┌─────────────────────┐
      │                     │            │                     │
      │     LLM Service     │            │  Summarization API  │
      │                     │            │                     │
      └─────────────────────┘            └─────────────────────┘
```

### Communication Flow

1. **User → UI Service**: User interacts with the frontend interface
2. **UI Service → EEP2**: Requests are forwarded to the Course Buddy service
3. **EEP2 handles all business logic**: Processing, analysis, and decision-making
4. **EEP2 → IEPs**: Simple calls to internal endpoints when AI capabilities are needed
5. **IEPs → External Models**: Minimal wrappers around API calls to external services
6. **Response flows back**: Results travel back up the chain to the user

## Internal End Points (IEPs)

IEPs are simple internal endpoints that act as thin communication layers between EEP2 and external AI services. **Important**: IEPs should contain minimal logic (essentially just model.predict(x)) and serve only as standardized connectors.

### IEP-LLM
- Simple wrapper around LLM API calls
- Forwards prompts from EEP2 to the LLM service
- Returns raw responses back to EEP2 for processing
- **Technical Tip**: Keep this as thin as possible, just handling API authentication and formatting

### IEP-Summarizer
- Connector to specialized summarization services
- Could use extractive summarization algorithms rather than just LLMs
- Examples include BART, TextRank, or other specialized summarization APIs
- **Technical Tip**: Consider text-specific summarization models that may be more efficient than general LLMs

## Business Logic in EEP2

All actual business logic and processing should be contained in EEP2 itself, not in the IEPs:

### Course Code Extraction
- Retrieves course codes from accessible storage (e.g., shared JSON file, database, or via API)
- EEP2 will check `latest_schedule.json` or make API calls to UI service to access the current schedule
- Extracts and processes the course codes to create course-specific workspaces
- **Technical Tip**: Implement polling or webhooks to detect when new course codes are added to the schedule

### Document Processing
- Extract text from various document formats
- Pre-process and chunk content for analysis
- Index content for efficient retrieval
- Identify key topics and concepts
- **Technical Tip**: Use libraries like PyPDF2, python-docx for parsing, and text-processing libraries for analysis

### Quiz Generation
- Determine important concepts for testing
- Formulate appropriate questions and answer options
- Process user responses to calculate knowledge score
- **Technical Tip**: Use NLP techniques to identify key testable concepts before sending to LLM

### Time Adjustment
- Analyze quiz results to determine knowledge gaps
- Calculate appropriate preparation time adjustments
- Generate explanations for suggested changes
- **Technical Tip**: Consider implementing a simple formula that correlates quiz performance to recommended study time

### Summarization Processing
- Determine what content needs summarization
- Choose appropriate summarization strategy (extractive vs. abstractive)
- Post-process summaries for readability and completeness
- **Technical Tip**: Different materials may benefit from different summarization approaches

### Q&A Processing
- Formulate effective prompts based on user questions
- Process and enhance LLM responses before presenting to user
- Maintain conversation context for coherent interactions
- **Technical Tip**: Implement retrieval-augmented generation by searching for relevant content before querying the LLM

## Technical Implementation Guidelines

### Data Flow

1. **Schedule Extraction**:
   ```
   UI → EEP2 (business logic) → Extract course codes → Create course tabs → UI
   ```

2. **Material Processing**:
   ```
   UI → EEP2 (business logic) → Process documents → IEP-LLM (if needed) → LLM → EEP2 → UI
   ```

3. **Quiz Generation**:
   ```
   UI → EEP2 (business logic) → Generate quiz structure → IEP-LLM → LLM → EEP2 → UI
   ```

4. **Time Adjustment**:
   ```
   EEP2 (business logic) → Calculate time adjustment → UI → User accepts/rejects
   ```

5. **Summarization**:
   ```
   UI → EEP2 (business logic) → IEP-Summarizer → Summarization API → EEP2 → UI
   ```

### AI Service Options

EEP2 can utilize various specialized services through IEPs:

1. **LLM Options**:
   - General-purpose: OpenAI API, Claude API, Llama 3
   - Domain-specific: Models fine-tuned for educational content

2. **Summarization Alternatives**:
   - Extractive summarization: TextRank, LexRank (non-LLM approaches)
   - Specialized models: BART, T5, Pegasus (more efficient than general LLMs)
   - Hybrid approaches: Extract key sentences then refine with smaller models

3. **Integration Approach**:
   - IEPs should be simple wrappers around these services
   - EEP2 decides which service to use for each task
   - Each model interaction should be stateless and focused

### State Management

- EEP2 maintains all state information (courses, materials, quiz results)
- IEPs are stateless and only handle individual requests
- Course materials are processed and stored by EEP2

## Git Workflow for Development

Follow these steps to create your own branch and work on implementing the EEP2 service:

### 1. Clone the Repository (if you haven't already)

```bash
git clone https://github.com/username/repo-name.git
cd repo-name
```

### 2. Make Sure You Have the Latest Changes

```bash
git checkout main
git pull origin main
```

### 3. Create a New Branch for Your Work

Choose a descriptive name for your branch that relates to what you're implementing:

```bash
git checkout -b feature/eep2-course-buddy
```

This creates a new branch called `feature/eep2-course-buddy` and switches to it.

### 4. Make Your Changes

Now you can create and modify files for the EEP2 service. Start with:

- Create the basic folder structure
- Implement the core EEP2 service with Flask
- Add simple IEP interfaces

### 5. Commit Your Changes Frequently

Make regular, small commits with descriptive messages:

```bash
# Check what files have been changed
git status

# Add specific files
git add EEP2/app.py EEP2/requirements.txt

# Or add all changes
git add .

# Commit with a descriptive message
git commit -m "feat: implement basic EEP2 service structure"
```

Use prefixes in your commit messages for clarity:
- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `refactor:` for code changes that neither fix bugs nor add features

### 6. Push Your Branch to GitHub

When you're ready to share your changes:

```bash
git push -u origin feature/eep2-course-buddy
```

The `-u` flag sets up tracking - you'll only need it the first time you push a new branch.

### 7. Update Your Branch with Latest Changes

If others are working on the project, periodically incorporate their changes:

```bash
# Switch to main and get updates
git checkout main
git pull origin main

# Switch back to your branch
git checkout feature/eep2-course-buddy

# Merge main into your branch
git merge main

# Resolve any conflicts if they arise
```

### 8. Create a Pull Request When Ready

When your implementation is complete:

1. Push your final changes: `git push origin feature/eep2-course-buddy`
2. Go to the repository on GitHub
3. Click "Compare & pull request" for your branch
4. Add a title and description explaining your changes
5. Request a review from a teammate
6. Click "Create pull request"

### Tips for Successful Collaboration

- **Commit Often**: Small, frequent commits are easier to understand and review
- **Update Regularly**: Pull from main frequently to avoid large merge conflicts
- **Write Clear Messages**: Commit messages should explain why changes were made
- **Test Thoroughly**: Make sure your code works before creating a pull request
- **Document Your Code**: Include comments and update this README as needed

## Implementation Roadmap

1. **Phase 1: Core Service**
   - Set up EEP2 service with course extraction logic
   - Implement material upload and storage
   - Create basic IEP interfaces for models

2. **Phase 2: Content Processing**
   - Implement document processing in EEP2
   - Connect IEP-LLM to chosen LLM provider
   - Build quiz generation logic in EEP2

3. **Phase 3: Advanced Features**
   - Add IEP-Summarizer with appropriate summarization service
   - Implement Q&A functionality in EEP2
   - Enhance user interface

## UI Integration

The UI should include these elements:

1. **Course Selection**:
   - Tabs generated from course codes in schedule
   - Only one active course tab at a time

2. **Material Management**:
   - Upload interface with drag-and-drop
   - Processing indicator and status

3. **Quiz Interface**:
   - Clear question presentation
   - Multiple-choice answer selection
   - Results with knowledge score

4. **Time Management**:
   - Suggested time adjustment with explanation
   - Accept/reject controls

5. **Learning Tools**:
   - Summary display with key concepts
   - Question input with conversation history

## Testing Approach

1. **EEP2 Business Logic Testing**:
   - Unit tests for each component
   - Mock IEP responses for deterministic testing

2. **IEP Testing**:
   - Verify correct formatting of requests to external services
   - Test error handling and retry mechanisms

3. **Integration Testing**:
   - Test the complete flow from UI through EEP2 and IEPs
   - Verify correct handling of various document types

4. **User Acceptance Testing**:
   - Validate quiz quality and relevance
   - Assess summary quality with different approaches
   - Evaluate time adjustment recommendations

## Getting Started

1. Start by implementing the core EEP2 service
2. Create simple IEP implementations that return mock data
3. Gradually replace mock IEPs with real integrations
4. Focus on the business logic within EEP2

## Example Workflow

1. User uploads schedule with courses "CMPS350" and "EECE503"
2. Course Buddy creates tabs for both courses
3. User selects "CMPS350" tab and uploads lecture slides
4. EEP2 processes slides and calls IEP-LLM to generate a quiz
5. User completes quiz, scoring 65%
6. EEP2 calculates and suggests increasing preparation time from 2 hours to 3 hours
7. User accepts change, schedule is updated
8. User requests a summary, and EEP2 calls IEP-Summarizer
9. User asks questions about concepts, and EEP2 formulates prompts for IEP-LLM

## Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [PyPDF2 Documentation](https://pypdf2.readthedocs.io/)
- [Hugging Face Transformers](https://huggingface.co/docs/transformers/index)
- [Sumy (TextRank implementation)](https://github.com/miso-belica/sumy)
- [LangChain Documentation](https://python.langchain.com/docs/get_started/introduction) 