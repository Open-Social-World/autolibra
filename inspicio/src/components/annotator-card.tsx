import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { AlertCircle } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";


interface AnnotatorCardProps {
  availableAgentIds: string[];
  onSubmit: (annotatorId: string, agentId: string) => void;
}

const AnnotatorCard: React.FC<AnnotatorCardProps> = ({ availableAgentIds = [], onSubmit }) => {
  const [annotatorIdInput, setAnnotatorIdInput] = useState<string>('');
  const [selectedAgentIdInput, setSelectedAgentIdInput] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = () => {
    setError(null); // Clear previous errors
    if (!annotatorIdInput.trim()) {
      setError("Please enter your Annotator ID.");
      return;
    }
    if (!selectedAgentIdInput) {
      setError("Please select an Agent ID to annotate.");
      return;
    }
    onSubmit(annotatorIdInput.trim(), selectedAgentIdInput);
  };

  // Filter out empty strings from agent IDs just in case
  const validAgentIds = availableAgentIds.filter(id => id !== '');

  return (
    <div className="flex items-center justify-center h-full p-4 bg-gray-50">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader>
          <CardTitle>Annotation Setup</CardTitle>
          <CardDescription>Enter your ID and select the agent you want to annotate for this instance.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
             <Alert variant="destructive">
               <AlertCircle className="h-4 w-4" />
               <AlertTitle>Error</AlertTitle>
               <AlertDescription>{error}</AlertDescription>
             </Alert>
          )}
          <div className="space-y-2">
            <Label htmlFor="annotatorId">Annotator ID</Label>
            <Input
              id="annotatorId"
              type="text"
              value={annotatorIdInput}
              onChange={(e) => setAnnotatorIdInput(e.target.value)}
              placeholder="Enter your unique annotator ID"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="agentSelectAnnotation">Agent to Annotate</Label>
            <Select
              value={selectedAgentIdInput}
              onValueChange={setSelectedAgentIdInput}
              required
            >
              <SelectTrigger id="agentSelectAnnotation">
                <SelectValue placeholder="Select Agent ID" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="placeholder-disabled" disabled>Select Agent ID</SelectItem>
                {validAgentIds.length > 0 ? (
                  validAgentIds.map(agentId => (
                    <SelectItem key={agentId} value={agentId}>
                      {agentId}
                    </SelectItem>
                  ))
                ) : (
                  <SelectItem value="no-agents" disabled>No agents available for this instance</SelectItem>
                )}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
        <CardFooter>
          <Button
            onClick={handleSubmit}
            className="w-full"
            disabled={!Array.isArray(availableAgentIds) || availableAgentIds.length === 0}
          >
            Start Annotating
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
};

export default AnnotatorCard; 