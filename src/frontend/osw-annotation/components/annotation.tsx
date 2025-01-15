import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type TrajectoryStep = {
  type: 'observation' | 'action';
  content: string;
  screenshot?: string;
  timestamp?: number;
};

type WebArenaInstance = {
  id: string;
  task: string;
  source_model: string;
  trajectory: TrajectoryStep[];
};

type FeedbackState = {
  success_rating: number;
  naturalness_rating: number;
  behavior_type: '' | 'efficient' | 'natural' | 'suboptimal';
  feedback_text: string;
};

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Slider } from "@/components/ui/slider";

const AnnotationInterface = () => {
  const [currentInstance, setCurrentInstance] = useState<WebArenaInstance | null>(null);
  const [feedback, setFeedback] = useState<FeedbackState>({
    success_rating: 0,
    naturalness_rating: 0,
    behavior_type: '',
    feedback_text: ''
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadRandomInstance = async () => {
    // In practice, this would fetch from your dataset
    try {
      const response = await fetch('/api/random-instance');
      const data = await response.json();
      setCurrentInstance(data);
    } catch (error) {
      console.error('Error loading instance:', error);
    }
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      await fetch('/api/submit-annotation', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          instanceId: currentInstance?.id,
          feedback
        }),
      });
      setFeedback({
        success_rating: 0,
        naturalness_rating: 0,
        behavior_type: '',
        feedback_text: ''
      });
      loadRandomInstance();
    } catch (error) {
      console.error('Error submitting annotation:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  useEffect(() => {
    loadRandomInstance();
  }, []);

  if (!currentInstance) {
    return <div className="flex justify-center items-center h-screen">Loading...</div>;
  }

  return (
    <div className="container mx-auto p-4">
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Task Details</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-lg font-medium mb-2">Task Description:</p>
          <p className="mb-4">{currentInstance.task}</p>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="font-medium">Instance ID: {currentInstance.id}</p>
              <p>Model: {currentInstance.source_model}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Trajectory Viewer</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="border rounded-lg p-4 mb-4 h-96 overflow-y-auto">
            {currentInstance.trajectory.map((step, index) => (
              <div key={index} className="mb-2 p-2 border-b">
                <div className="font-medium">{step.type}</div>
                <div className="text-sm">{step.content}</div>
                {step.screenshot && (
                  <img
                    src={step.screenshot}
                    alt={`Step ${index}`}
                    className="mt-2 max-w-full h-auto"
                  />
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Provide Feedback</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">

            <div>
              <Label>Detailed Feedback</Label>
              <Textarea
                className="mt-2"
                placeholder="Provide your detailed feedback here..."
                value={feedback.feedback_text}
                onChange={(e) => setFeedback(prev => ({ ...prev, feedback_text: e.target.value }))}
                rows={4}
              />
            </div>

            <div className="flex space-x-4">
              <Button
                onClick={handleSubmit}
                disabled={isSubmitting}
              >
                Submit Feedback
              </Button>
              <Button
                variant="outline"
                onClick={loadRandomInstance}
                disabled={isSubmitting}
              >
                Skip Instance
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AnnotationInterface;
