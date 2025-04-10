import React, { useState, useEffect } from 'react';
import { 
  Box, 
  Container, 
  Typography, 
  Button, 
  TextField, 
  Paper, 
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  FormControlLabel,
  RadioGroup,
  Radio,
  InputLabel,
  Input,
  FormHelperText,
  ThemeProvider,
  createTheme,
  Select,
  MenuItem,
  Grid,
  Card,
  CardContent,
  Chip,
  IconButton,
  Stack,
  Divider,
  useTheme,
  Alert
} from '@mui/material';
import { toast } from 'react-toastify';
import { LocalizationProvider, TimePicker } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { Add as AddIcon, Edit as EditIcon, Schedule as ScheduleIcon } from '@mui/icons-material';

// Create a modern theme
const theme = createTheme({
  palette: {
    primary: {
      main: '#2563eb',
      light: '#60a5fa',
      dark: '#1d4ed8',
    },
    secondary: {
      main: '#4f46e5',
      light: '#818cf8',
      dark: '#4338ca',
    },
    background: {
      default: '#f8fafc',
      paper: '#ffffff',
    },
    text: {
      primary: '#1e293b',
      secondary: '#64748b',
    }
  },
  typography: {
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    h4: {
      fontWeight: 700,
      letterSpacing: '-0.02em',
    },
    h6: {
      fontWeight: 600,
      letterSpacing: '-0.01em',
    },
    subtitle1: {
      fontWeight: 500,
    }
  },
  shape: {
    borderRadius: 12,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
          padding: '10px 20px',
          borderRadius: '8px',
          '&:hover': {
            transform: 'translateY(-1px)',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
          },
          transition: 'all 0.2s ease-in-out',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
          '&:hover': {
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
          },
          transition: 'all 0.2s ease-in-out',
        },
      },
    },
  },
});

const ScheduleCard = ({ event, type }) => {
  const theme = useTheme();
  
  return (
    <Card 
      sx={{ 
        mb: 2,
        borderLeft: `4px solid ${type === 'meeting' ? theme.palette.primary.main : theme.palette.secondary.main}`,
      }}
    >
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
            {event.description}
          </Typography>
          <Chip 
            label={event.priority} 
            size="small"
            color={event.priority === 'high' ? 'error' : event.priority === 'medium' ? 'warning' : 'success'}
          />
        </Stack>
        <Stack direction="row" spacing={2} mt={1}>
          <Typography variant="body2" color="text.secondary">
            {event.day} at {event.time || 'Flexible'}
          </Typography>
          {event.duration_minutes && (
            <Typography variant="body2" color="text.secondary">
              {Math.floor(event.duration_minutes / 60)}h {event.duration_minutes % 60}m
            </Typography>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
};

const QuestionDialog = ({ open, questions, onClose, onSubmit, isLoading, title }) => {
  const [answers, setAnswers] = useState({});
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);

  useEffect(() => {
    // Reset answers and current question when questions change
    setAnswers({});
    setCurrentQuestionIndex(0);
  }, [questions]);

  const currentQuestion = questions[currentQuestionIndex];

  const handleChange = (value) => {
    setAnswers(prev => ({
      ...prev,
      [currentQuestion.id]: value
    }));
  };

  const handleNext = () => {
    if (currentQuestionIndex < questions.length - 1) {
      setCurrentQuestionIndex(prev => prev + 1);
    } else {
      onSubmit(answers);
    }
  };

  const getButtonText = () => {
    if (isLoading) return <CircularProgress size={20} />;
    return currentQuestionIndex < questions.length - 1 ? 'Next' : 'Submit';
  };

  if (!currentQuestion) return null;

  return (
    <Dialog 
      open={open} 
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 2,
          p: 1
        }
      }}
    >
      <DialogTitle sx={{ pb: 1 }}>
        {title || `Question ${currentQuestionIndex + 1} of ${questions.length}`}
      </DialogTitle>
      <DialogContent>
        <Box sx={{ py: 2 }}>
          <Typography variant="h6" gutterBottom color="primary" sx={{ mb: 3 }}>
            {currentQuestion.text}
          </Typography>
          <FormControl component="fieldset" fullWidth>
            <RadioGroup
              value={answers[currentQuestion.id] || ''}
              onChange={(e) => handleChange(e.target.value)}
            >
              {currentQuestion.options?.map((option) => (
                <FormControlLabel
                  key={option}
                  value={option}
                  control={<Radio />}
                  label={option}
                  sx={{ 
                    mb: 1,
                    p: 1.5,
                    width: '100%',
                    border: '1px solid',
                    borderColor: 'divider',
                    borderRadius: 1,
                    '&:hover': {
                      backgroundColor: 'action.hover',
                      borderColor: 'primary.main',
                    },
                    ...(answers[currentQuestion.id] === option && {
                      backgroundColor: 'primary.lighter',
                      borderColor: 'primary.main',
                    })
                  }}
                />
              ))}
            </RadioGroup>
          </FormControl>
        </Box>
      </DialogContent>
      <DialogActions sx={{ p: 2, pt: 0 }}>
        <Button onClick={onClose} color="inherit">Cancel</Button>
        <Button 
          variant="contained" 
          onClick={handleNext}
          disabled={isLoading || !answers[currentQuestion.id]}
        >
          {getButtonText()}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

const Dashboard = () => {
  const [scheduleText, setScheduleText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [parsedSchedule, setParsedSchedule] = useState(null);

  const handleGenerateSchedule = async () => {
    if (!scheduleText.trim()) {
      toast.error('Please enter your schedule');
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch('http://localhost:5000/parse-schedule', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: scheduleText })
      });

      const data = await response.json();
      
      if (response.ok) {
        setParsedSchedule(data.schedule);
        toast.success('Schedule parsed successfully!');
      } else {
        toast.error(data.error || 'Failed to parse schedule');
      }
    } catch (error) {
      console.error('Error:', error);
      toast.error('Failed to parse schedule');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <ThemeProvider theme={theme}>
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Box sx={{ mb: 4 }}>
          <Typography variant="h4" gutterBottom>
            Schedule Parser
          </Typography>
        </Box>

        {/* Create Schedule Section */}
        <Paper sx={{ p: 3, mb: 4 }}>
          <Typography variant="h6" gutterBottom>
            Create Schedule
          </Typography>
          <TextField
            fullWidth
            multiline
            rows={4}
            variant="outlined"
            placeholder="Enter your schedule details..."
            value={scheduleText}
            onChange={(e) => setScheduleText(e.target.value)}
            sx={{ mb: 2 }}
          />
          <Button
            variant="contained"
            onClick={handleGenerateSchedule}
            disabled={isLoading}
            startIcon={isLoading ? <CircularProgress size={20} /> : <AddIcon />}
          >
            Generate Schedule
          </Button>
        </Paper>

        {/* Display Parsed Schedule */}
        {parsedSchedule && (
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Parsed Schedule
            </Typography>
            <Box sx={{ 
              backgroundColor: '#f5f5f5', 
              p: 2, 
              borderRadius: 1,
              maxHeight: '500px',
              overflow: 'auto'
            }}>
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                {JSON.stringify(parsedSchedule, null, 2)}
              </pre>
            </Box>
          </Paper>
        )}
      </Container>
    </ThemeProvider>
  );
};

export default Dashboard; 