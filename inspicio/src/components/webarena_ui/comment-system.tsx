import React, { useState, useRef, useEffect } from 'react';
import { User, MessageSquare, X, Send, Trash2, Edit, Loader2, LogIn } from 'lucide-react';
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

// Define props interface
interface CommentSystemProps {
  initialText: string;
  isLoading?: boolean;
  instanceId: string | null;
  agentId: string;
}

// Define comment structure (Combine elements from both versions)
interface Comment {
    id: string;
    text: string;
    selection: {
        text: string;
        startOffset: number;
        endOffset: number;
    };
    user: string; // Annotator ID
    timestamp: Date;
    replies: Reply[];
    isSaving?: boolean; // Keep for backend status
    saveError?: string | null; // Keep for backend status
}

interface Reply { // Keep Reply interface
    id: string;
    text: string;
    user: string;
    timestamp: Date;
}

// Main component
const CommentSystem: React.FC<CommentSystemProps> = ({
    initialText,
    isLoading = false,
    instanceId,
    agentId
}) => {
  const [text, setText] = useState(initialText);
  const [selection, setSelection] = useState<any>(null); // Keep state
  const [comments, setComments] = useState<Comment[]>([]); // Keep state
  const [activeComment, setActiveComment] = useState<string | null>(null); // Keep state
  const [newComment, setNewComment] = useState(''); // Keep state
  const [editingComment, setEditingComment] = useState<string | null>(null); // Keep state
  const textRef = useRef<HTMLDivElement>(null); // Keep ref
  const commentInputRef = useRef<HTMLInputElement>(null); // Keep ref
  const [isSubmitting, setIsSubmitting] = useState(false); // Keep state
  const [submitError, setSubmitError] = useState<string | null>(null); // Keep state
  const [annotatorId, setAnnotatorId] = useState<string>(''); // Keep state
  const [isAnnotatorIdSet, setIsAnnotatorIdSet] = useState<boolean>(false); // Keep state

  // Reset comments when initialText changes (Keep this effect)
  useEffect(() => {
    setText(initialText);
    setComments([]);
    setSelection(null);
    setActiveComment(null);
    setNewComment('');
    setEditingComment(null);
    setSubmitError(null);
  }, [initialText]);

  // Handle setting the annotator ID (Keep this handler)
  const handleAnnotatorIdSubmit = () => {
      if (annotatorId.trim()) {
          setIsAnnotatorIdSet(true);
      }
  }

  // Handle text selection - Revert to older positioning logic, keep annotator check
  const handleTextSelection = () => {
    if (!isAnnotatorIdSet) { // Keep this check
        setSelection(null);
        return;
    }

    const selectionObj = window.getSelection();
    // Use older logic for checking selection and calculating position/offsets
    if (selectionObj && selectionObj.toString().length > 0 && textRef.current && textRef.current.contains(selectionObj.anchorNode)) {
      const range = selectionObj.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      const textRect = textRef.current.getBoundingClientRect(); // Need container rect

      const preSelectionRange = document.createRange();
      preSelectionRange.selectNodeContents(textRef.current);
      preSelectionRange.setEnd(range.startContainer, range.startOffset);
      const startOffset = preSelectionRange.toString().length;
      const endOffset = startOffset + range.toString().length;

      setSelection({
        text: selectionObj.toString(),
        startOffset: startOffset,
        endOffset: endOffset,
        // Use older relative positioning logic
        position: {
          left: rect.right - textRect.left, // Position relative to textRef
          top: rect.top - textRect.top     // Position relative to textRef
        }
      });
      setSubmitError(null); // Clear previous errors
    } else {
      setSelection(null);
    }
  };

  // Add a new comment - Revert optimistic update logic, keep async fetch
  const addComment = async () => {
    // Keep validation
    if (!instanceId || !isAnnotatorIdSet || !annotatorId.trim() || !selection || !newComment.trim()) {
        console.error("Validation failed in addComment");
        setSubmitError("Cannot add comment: Missing required information or Annotator ID not set.");
        return;
    }

    setIsSubmitting(true);
    setSubmitError(null);

    // Data for backend (Keep this)
    const commentData = {
      instance_id: instanceId,
      agent_id: agentId,
      annotator_id: annotatorId.trim(),
      comment_text: newComment,
      selection_text: selection.text,
      start_offset: selection.startOffset,
      end_offset: selection.endOffset,
    };

    // Create the comment object similar to the older version
    const tempId = `temp-${Date.now()}`; // Use temp ID for optimistic update
    const comment: Comment = {
      id: tempId,
      text: newComment,
      selection: { // Ensure structure matches Comment interface
        text: selection.text,
        startOffset: selection.startOffset,
        endOffset: selection.endOffset
      },
      user: annotatorId.trim(), // Use the set annotator ID
      timestamp: new Date(),
      replies: [],
      isSaving: true, // Mark as saving for optimistic UI
      saveError: null
    };

    // Optimistic update - Directly add the new comment object (like older version)
    setComments(prevComments => [...prevComments, comment]);

    // Reset form state
    setNewComment('');
    setSelection(null); // Close popover
    // Optionally activate the new comment
    // setActiveComment(comment.id);

    // --- Keep Backend Fetch Logic ---
    try {
      const response = await fetch('http://localhost:8000/annotations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(commentData),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to parse error response.' }));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      // Update comment state on success (remove saving flag)
      setComments(prev => prev.map(c => c.id === tempId ? { ...c, isSaving: false } : c));

    } catch (error) {
      console.error('Failed to save comment:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setSubmitError(`Failed to save: ${errorMessage}`);
      // Update comment state on error (add error flag/message)
      setComments(prev => prev.map(c => c.id === tempId ? { ...c, isSaving: false, saveError: errorMessage } : c));
    } finally {
      setIsSubmitting(false);
    }
  };

  // Edit a comment (Keep current logic, seems standard)
  const updateComment = (id: string, newText: string) => {
    // Add backend update logic here if needed
    setComments(
      comments.map(comment =>
        comment.id === id
          ? { ...comment, text: newText }
          : comment
      )
    );
    setEditingComment(null);
  };

  // Delete a comment (Keep current logic, seems standard)
  const deleteComment = (id: string) => {
    // Add backend delete logic here if needed
    setComments(comments.filter(comment => comment.id !== id));
    if (activeComment === id) {
        setActiveComment(null);
    }
  };

  // Add a reply (Keep current logic, seems standard)
  const addReply = (commentId: string, replyText: string) => {
    // Add backend reply logic here if needed
    if (replyText.trim()) {
      setComments(
        comments.map(comment =>
          comment.id === commentId
            ? {
                ...comment,
                replies: [
                  ...comment.replies,
                  {
                    id: `reply-${Date.now()}`, // Use temp ID
                    text: replyText,
                    user: annotatorId.trim(), // Use annotator ID
                    timestamp: new Date()
                  }
                ]
              }
            : comment
        )
      );
    }
  };

  // Handle clicking on highlighted text (Keep current logic)
  const handleHighlightClick = (commentId: string) => {
    setActiveComment(activeComment === commentId ? null : commentId);
    // Optional: Scroll comment into view in the sidebar
    const commentElement = document.getElementById(`comment-card-${commentId}`);
    commentElement?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  // Focus on comment input when selection changes (Keep current logic)
  useEffect(() => {
    if (selection && commentInputRef.current) {
      commentInputRef.current.focus();
    }
  }, [selection]);

  // Format date utility (Keep this)
  const formatDate = (date: Date): string => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  // Render highlighted text - Revert to older logic
  const renderHighlightedText = () => {
    if (isLoading) { // Keep loading state
        return <div className="p-4 text-muted-foreground">Loading text...</div>;
    }
    if (!text) { // Keep check for empty text
        return <div className="p-4 text-muted-foreground">No text content available.</div>;
    }

    // Use older sorting and mapping logic
    const sortedComments = [...comments].sort((a, b) =>
      a.selection.startOffset - b.selection.startOffset // Sort ascending for sequential processing
    );

    const parts: (string | JSX.Element)[] = [];
    let lastIndex = 0;

    sortedComments.forEach(comment => {
        const { startOffset, endOffset } = comment.selection;
        // Add text before the highlight
        if (startOffset > lastIndex) {
            parts.push(text.substring(lastIndex, startOffset));
        }
        // Add the highlighted span (use older class names or adapt)
        parts.push(
            <span
                key={comment.id}
                // Use classes similar to older version or current ones if preferred
                className={`highlighted-text cursor-pointer rounded px-0.5 transition-all ${
                    activeComment === comment.id ? 'bg-blue-200 ring-1 ring-blue-400' : 'bg-blue-100 hover:bg-blue-200' // Example classes
                } ${comment.isSaving ? 'opacity-60 animate-pulse' : ''} ${comment.saveError ? 'bg-red-200 ring-1 ring-red-400' : ''}`} // Add saving/error styles
                onClick={(e) => {
                    e.stopPropagation(); // Prevent text selection handler
                    handleHighlightClick(comment.id);
                }}
                title={comment.saveError ? `Error: ${comment.saveError}` : undefined} // Show error on hover
            >
                {text.substring(startOffset, endOffset)}
            </span>
        );
        lastIndex = endOffset;
    });

    // Add any remaining text after the last highlight
    if (lastIndex < text.length) {
        parts.push(text.substring(lastIndex));
    }

    // Return the div containing the parts
    return <div className="whitespace-pre-wrap p-4">{parts.map((part, index) => <React.Fragment key={index}>{part}</React.Fragment>)}</div>;
  };


  return (
    // Use current outer structure
    <div className="flex h-full">
        {/* Text display area - Use current structure */}
        <div className="flex-1 overflow-y-auto relative" ref={textRef} onMouseUp={handleTextSelection}>
          {renderHighlightedText()}

          {/* Selection Popover - Revert to older structure/style */}
          {selection && isAnnotatorIdSet && ( // Keep annotator check
            <div
              className="absolute flex items-center bg-white border rounded-lg shadow-lg p-2 z-10" // Style similar to older version
              style={{
                top: `${selection.position.top + textRef.current?.scrollTop + 10}px`, // Adjust top based on scroll + offset
                left: `${selection.position.left + textRef.current?.scrollLeft}px` // Adjust left based on scroll
              }}
              onClick={(e) => e.stopPropagation()} // Prevent closing on click inside
              onMouseDown={(e) => e.stopPropagation()} // Prevent text selection trigger
            >
              <div className="flex items-center space-x-2">
                <input
                  ref={commentInputRef}
                  type="text"
                  value={newComment}
                  onChange={(e) => setNewComment(e.target.value)}
                  placeholder="Add a comment..."
                  className="border rounded px-2 py-1 text-sm" // Style similar to older version
                  autoFocus // Keep autoFocus
                  onKeyDown={(e) => { if (e.key === 'Enter') { addComment(); } }}
                />
                <Button // Use Button component
                  onClick={addComment}
                  size="sm" // Use size prop
                  disabled={isSubmitting || !newComment.trim()} // Keep disabled logic
                >
                  {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send size={16} />}
                </Button>
                <Button // Use Button component for close
                    onClick={() => setSelection(null)}
                    variant="ghost" // Use ghost variant
                    size="sm"
                    className="p-1"
                >
                  <X size={16} />
                </Button>
              </div>
               {/* Display submit error inside popover */}
               {submitError && <p className="text-xs text-red-600 mt-1 w-full text-center">{submitError}</p>}
            </div>
          )}
        </div>

        {/* Comments sidebar - Use current structure but older rendering logic inside */}
        <div className="w-80 border-l bg-gray-50 overflow-y-auto flex flex-col">
          {/* Sidebar Header - Keep current header with Annotator ID */}
          <div className="p-3 border-b sticky top-0 bg-gray-50 z-10">
             <h3 className="text-sm font-semibold mb-2 text-center">
                Comments (Agent: {agentId})
             </h3>
             {/* Annotator ID Input Area */}
             <div className="flex items-end space-x-2">
                 <div className="flex-grow">
                     <Label htmlFor={`annotator-id-${agentId}`} className="text-xs font-medium text-gray-600">Annotator ID:</Label>
                     <Input
                         id={`annotator-id-${agentId}`}
                         type="text"
                         placeholder="Your ID"
                         value={annotatorId}
                         onChange={(e) => setAnnotatorId(e.target.value)}
                         className="h-8 text-sm mt-1"
                         disabled={isAnnotatorIdSet}
                         onKeyDown={(e) => { if (e.key === 'Enter') handleAnnotatorIdSubmit(); }}
                     />
                 </div>
                 <Button
                     onClick={handleAnnotatorIdSubmit}
                     size="sm"
                     variant="outline"
                     className="h-8"
                     disabled={isAnnotatorIdSet || !annotatorId.trim()}
                     title={isAnnotatorIdSet ? "Annotator ID is set" : "Set Annotator ID"}
                 >
                     <LogIn size={14} />
                 </Button>
             </div>
             {/* Helper text for Annotator ID */}
             {!isAnnotatorIdSet && annotatorId.trim() && ( <p className="text-xs text-muted-foreground mt-1">Press Enter or click button to set ID.</p> )}
             {!isAnnotatorIdSet && !annotatorId.trim() && ( <p className="text-xs text-muted-foreground mt-1">Enter your Annotator ID to enable commenting.</p> )}
          </div>

          {/* Comments List Area - Use older rendering logic */}
          <div className="p-4 space-y-4 flex-grow"> {/* Remove overflow-y-auto if parent handles scroll */}
            {comments.length === 0 ? (
              // Use older "No comments yet" structure
              <div className="text-center text-gray-500 py-8">
                <MessageSquare className="mx-auto mb-2" size={24} />
                <p>No comments yet</p>
                {isAnnotatorIdSet ? (
                    <p className="text-sm">Highlight text to add a comment</p>
                ) : (
                    <p className="text-sm text-orange-600">Set Annotator ID above to comment</p> // Keep prompt to set ID
                )}
              </div>
            ) : (
              // Use older map structure for comments
              comments.map(comment => (
                <div
                  id={`comment-card-${comment.id}`} // Keep ID for scrolling
                  key={comment.id}
                  // Use older class structure or adapt current ones
                  className={`border rounded-lg p-3 cursor-pointer transition-all relative ${activeComment === comment.id ? 'bg-white shadow-md ring-2 ring-blue-300' : 'bg-gray-100 hover:bg-gray-200'} ${comment.saveError ? 'ring-2 ring-red-400 bg-red-50' : ''}`} // Keep error styling
                  onClick={() => handleHighlightClick(comment.id)}
                >
                   {/* Saving/Error Indicators (Keep these) */}
                   {comment.isSaving && ( <div className="absolute top-1 right-1 p-1 rounded-full bg-blue-100"> <Loader2 size={12} className="animate-spin text-blue-600" /> </div> )}
                   {comment.saveError && ( <div className="absolute top-1 right-1 p-1 rounded-full bg-red-100" title={comment.saveError}> <X size={12} className="text-red-600" /> </div> )}

                  {/* Comment Header (User, Timestamp, Actions) - Use older structure */}
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center">
                      <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white mr-2"> <User size={16} /> </div>
                      <div>
                        <div className="font-medium text-sm">{comment.user}</div> {/* Shows annotatorId */}
                        <div className="text-xs text-gray-500">{formatDate(comment.timestamp)}</div>
                      </div>
                    </div>
                    {/* Actions - Use older structure */}
                    <div className="flex space-x-1">
                      <button onClick={(e) => { e.stopPropagation(); setEditingComment(comment.id); }} className="text-gray-500 hover:text-gray-700 p-1 rounded hover:bg-gray-300 disabled:opacity-50" disabled={!!comment.isSaving || !!comment.saveError}> <Edit size={14} /> </button>
                      <button onClick={(e) => { e.stopPropagation(); deleteComment(comment.id); }} className="text-gray-500 hover:text-red-500 p-1 rounded hover:bg-gray-300 disabled:opacity-50" disabled={!!comment.isSaving}> <Trash2 size={14} /> </button>
                    </div>
                  </div>

                  {/* Highlighted text snippet - Use older structure */}
                   <blockquote className="text-xs text-gray-600 border-l-2 pl-2 italic my-1 truncate"> "{comment.selection.text}" </blockquote>

                  {/* Comment Body (View/Edit) - Use older structure */}
                  <div className="mb-2">
                    {editingComment === comment.id ? (
                      <div className="mt-1">
                        <textarea defaultValue={comment.text} className="w-full p-2 border rounded text-sm" rows={3} autoFocus onClick={(e) => e.stopPropagation()} onBlur={(e) => updateComment(comment.id, e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); updateComment(comment.id, e.target.value); } else if (e.key === 'Escape') { setEditingComment(null); } }} />
                      </div>
                    ) : ( <p className="text-sm whitespace-pre-wrap">{comment.text}</p> )}
                  </div>

                  {/* Replies Section - Use older structure */}
                  <div className="mt-2 pl-3 border-l-2 border-gray-200 space-y-2">
                    {comment.replies.map((reply: Reply) => ( <div key={reply.id} className="text-xs py-1"> <div className="flex items-center mb-1"> <div className="w-5 h-5 rounded-full bg-gray-400 flex items-center justify-center text-white mr-1.5"> <User size={10} /> </div> <div className="font-medium mr-1">{reply.user}</div> <div className="text-gray-500">{formatDate(reply.timestamp)}</div> </div> <p className="pl-6">{reply.text}</p> </div> ))}
                    {/* Reply Input - Show only when comment is active */}
                    {activeComment === comment.id && ( <div className="flex items-center mt-2 pt-2 border-t border-gray-200"> <input type="text" placeholder="Reply..." className="flex-1 border rounded-l px-2 py-1 text-xs" onClick={(e) => e.stopPropagation()} onKeyDown={(e) => { if (e.key === 'Enter' && (e.target as HTMLInputElement).value.trim()) { addReply(comment.id, (e.target as HTMLInputElement).value); (e.target as HTMLInputElement).value = ''; } }} /> <button className="bg-blue-500 text-white rounded-r p-1 text-xs hover:bg-blue-600" onClick={(e) => { e.stopPropagation(); const input = (e.target as HTMLElement).closest('div')?.querySelector('input'); if (input && input.value.trim()) { addReply(comment.id, input.value); input.value = ''; } }}> Reply </button> </div> )}
                  </div>
                </div>
              )) // End comments.map
            )} {/* End Conditional Rendering */}
          </div> {/* End Comments List Container */}
        </div> {/* End Comments Sidebar */}
      </div> // End Main Flex Container
  );
};

export default CommentSystem;