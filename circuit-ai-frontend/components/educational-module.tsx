"use client";

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { 
  BookOpen, 
  Play, 
  Pause, 
  CheckCircle, 
  XCircle, 
  ArrowRight, 
  Award,
  Lightbulb,
  Target
} from 'lucide-react';
import { EducationalContent, QuizQuestion } from '@/types/analysis';

interface EducationalModuleProps {
  content: EducationalContent;
  onComplete?: (score: number) => void;
  className?: string;
}

export function EducationalModule({ content, onComplete, className }: EducationalModuleProps) {
  const [currentStep, setCurrentStep] = useState<'content' | 'quiz' | 'complete'>('content');
  const [quizAnswers, setQuizAnswers] = useState<Record<string, number>>({});
  const [showResults, setShowResults] = useState(false);
  const [score, setScore] = useState(0);

  const handleQuizAnswer = (questionId: string, answerIndex: number) => {
    setQuizAnswers(prev => ({
      ...prev,
      [questionId]: answerIndex
    }));
  };

  const calculateScore = () => {
    if (!content.quiz_questions) return 0;
    
    let correct = 0;
    content.quiz_questions.forEach(question => {
      if (quizAnswers[question.id] === question.correct_answer) {
        correct++;
      }
    });
    
    return Math.round((correct / content.quiz_questions.length) * 100);
  };

  const handleCompleteQuiz = () => {
    const finalScore = calculateScore();
    setScore(finalScore);
    setShowResults(true);
    setCurrentStep('complete');
    onComplete?.(finalScore);
  };

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case 'beginner': return 'text-green-600 bg-green-100';
      case 'intermediate': return 'text-yellow-600 bg-yellow-100';
      case 'advanced': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
            <BookOpen className="w-5 h-5 text-white" />
          </div>
          <div>
            <CardTitle>{content.title}</CardTitle>
            <CardDescription>
              Learn about {content.component_type} components
            </CardDescription>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getDifficultyColor(content.difficulty)}`}>
            {content.difficulty}
          </span>
          {content.quiz_questions && (
            <span className="text-sm text-gray-600">
              {content.quiz_questions.length} questions
            </span>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {currentStep === 'content' && (
          <div className="space-y-4">
            <div className="prose prose-sm max-w-none">
              <p className="text-gray-700 leading-relaxed">{content.content}</p>
            </div>
            
            {content.video_url && (
              <div className="bg-gray-100 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Play className="w-4 h-4 text-blue-600" />
                  <span className="font-medium">Video Tutorial</span>
                </div>
                <p className="text-sm text-gray-600">Watch the interactive tutorial</p>
                <Button variant="outline" size="sm" className="mt-2">
                  <Play className="w-4 h-4 mr-2" />
                  Watch Video
                </Button>
              </div>
            )}
            
            {content.interactive_demo && (
              <div className="bg-gray-100 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Target className="w-4 h-4 text-green-600" />
                  <span className="font-medium">Interactive Demo</span>
                </div>
                <p className="text-sm text-gray-600">Try the interactive simulation</p>
                <Button variant="outline" size="sm" className="mt-2">
                  <Target className="w-4 h-4 mr-2" />
                  Launch Demo
                </Button>
              </div>
            )}
            
            <div className="flex justify-between pt-4">
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <Lightbulb className="w-4 h-4" />
                <span>Ready to test your knowledge?</span>
              </div>
              <Button 
                onClick={() => setCurrentStep('quiz')}
                disabled={!content.quiz_questions}
              >
                Start Quiz
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </div>
          </div>
        )}

        {currentStep === 'quiz' && content.quiz_questions && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Quiz Progress</span>
              <span className="text-sm text-gray-600">
                {Object.keys(quizAnswers).length} / {content.quiz_questions.length} answered
              </span>
            </div>
            
            <Progress 
              value={(Object.keys(quizAnswers).length / content.quiz_questions.length) * 100} 
              className="h-2"
            />
            
            {content.quiz_questions.map((question, index) => (
              <div key={question.id} className="space-y-3">
                <h4 className="font-medium">
                  Question {index + 1}: {question.question}
                </h4>
                <div className="space-y-2">
                  {question.options.map((option, optionIndex) => (
                    <button
                      key={optionIndex}
                      onClick={() => handleQuizAnswer(question.id, optionIndex)}
                      className={`w-full p-3 text-left rounded-lg border transition-colors ${
                        quizAnswers[question.id] === optionIndex
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <span className="font-medium mr-2">
                        {String.fromCharCode(65 + optionIndex)}.
                      </span>
                      {option}
                    </button>
                  ))}
                </div>
              </div>
            ))}
            
            <div className="flex justify-between pt-4">
              <Button 
                variant="outline" 
                onClick={() => setCurrentStep('content')}
              >
                Back to Content
              </Button>
              <Button 
                onClick={handleCompleteQuiz}
                disabled={Object.keys(quizAnswers).length < content.quiz_questions.length}
              >
                Complete Quiz
                <CheckCircle className="w-4 h-4 ml-2" />
              </Button>
            </div>
          </div>
        )}

        {currentStep === 'complete' && showResults && (
          <div className="text-center space-y-6">
            <div className="w-20 h-20 bg-gradient-to-r from-green-500 to-emerald-600 rounded-full flex items-center justify-center mx-auto">
              <Award className="w-10 h-10 text-white" />
            </div>
            
            <div>
              <h3 className="text-2xl font-bold mb-2">Quiz Complete!</h3>
              <p className="text-gray-600">You've completed the {content.title} module</p>
            </div>
            
            <div className="bg-gray-50 rounded-lg p-6">
              <div className="text-4xl font-bold mb-2">
                <span className={getScoreColor(score)}>{score}%</span>
              </div>
              <p className="text-gray-600">
                {score >= 80 ? 'Excellent work!' : score >= 60 ? 'Good job!' : 'Keep practicing!'}
              </p>
            </div>
            
            {content.quiz_questions && (
              <div className="space-y-3">
                <h4 className="font-medium">Review Answers:</h4>
                {content.quiz_questions.map((question, index) => {
                  const userAnswer = quizAnswers[question.id];
                  const isCorrect = userAnswer === question.correct_answer;
                  
                  return (
                    <div key={question.id} className="text-left p-3 bg-gray-50 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        {isCorrect ? (
                          <CheckCircle className="w-4 h-4 text-green-600" />
                        ) : (
                          <XCircle className="w-4 h-4 text-red-600" />
                        )}
                        <span className="font-medium">Question {index + 1}</span>
                      </div>
                      <p className="text-sm text-gray-700 mb-2">{question.question}</p>
                      <p className="text-xs text-gray-600">
                        <span className="font-medium">Your answer:</span> {question.options[userAnswer]}
                      </p>
                      {!isCorrect && (
                        <p className="text-xs text-green-600 mt-1">
                          <span className="font-medium">Correct answer:</span> {question.options[question.correct_answer]}
                        </p>
                      )}
                      <p className="text-xs text-gray-500 mt-2">{question.explanation}</p>
                    </div>
                  );
                })}
              </div>
            )}
            
            <Button 
              onClick={() => {
                setCurrentStep('content');
                setQuizAnswers({});
                setShowResults(false);
              }}
              variant="outline"
            >
              Review Content Again
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
