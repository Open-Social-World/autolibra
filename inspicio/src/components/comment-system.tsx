import React, { useState, useRef, useEffect } from 'react';
import { User, MessageSquare, X, Send, Trash2, Edit } from 'lucide-react';

// Define props interface
interface CommentSystemProps {
  initialText: string;
  isLoading?: boolean; // Optional prop to show loading state
}

// Main component
const CommentSystem: React.FC<CommentSystemProps> = ({ initialText, isLoading = false }) => {
  const [text, setText] = useState(initialText);
  const [selection, setSelection] = useState<any>(null); // Use 'any' or define a specific type
  const [comments, setComments] = useState<any[]>([]); // Use 'any' or define a specific type
  const [activeComment, setActiveComment] = useState<string | null>(null);
  const [newComment, setNewComment] = useState('');
  const [editingComment, setEditingComment] = useState<string | null>(null);
  const textRef = useRef<HTMLDivElement>(null);
  const commentInputRef = useRef<HTMLInputElement>(null);

  // Update text and reset comments when initialText prop changes
  useEffect(() => {
    setText(initialText);
    setComments([]); // Reset comments when text changes
    setSelection(null);
    setActiveComment(null);
    setNewComment('');
    setEditingComment(null);
  }, [initialText]);

  // Handle text selection
  const handleTextSelection = () => {
    const selectionObj = window.getSelection();

    if (selectionObj && selectionObj.toString().length > 0 && textRef.current?.contains(selectionObj.anchorNode)) {
      const range = selectionObj.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      const textRect = textRef.current.getBoundingClientRect();

      // Calculate offsets relative to the textRef container
      const preSelectionRange = document.createRange();
      preSelectionRange.selectNodeContents(textRef.current);
      preSelectionRange.setEnd(range.startContainer, range.startOffset);
      const startOffset = preSelectionRange.toString().length;
      const endOffset = startOffset + range.toString().length;


      setSelection({
        text: selectionObj.toString(),
        startOffset: startOffset, // Use calculated offset
        endOffset: endOffset,     // Use calculated offset
        position: {
          left: rect.right - textRect.left,
          top: rect.top - textRect.top
        }
      });
    } else {
      setSelection(null);
    }
  };

  // Add a new comment
  const addComment = () => {
    if (selection && newComment.trim()) {
      const comment = {
        id: Date.now().toString(),
        text: newComment,
        selection: {
          text: selection.text,
          startOffset: selection.startOffset,
          endOffset: selection.endOffset
        },
        user: "Current User", // Replace with actual user info if available
        timestamp: new Date(),
        replies: []
      };

      setComments([...comments, comment]);
      setNewComment('');
      setSelection(null);
      setActiveComment(comment.id);
    }
  };

  // Edit a comment
  const updateComment = (id: string, newText: string) => {
    setComments(
      comments.map(comment =>
        comment.id === id
          ? { ...comment, text: newText }
          : comment
      )
    );
    setEditingComment(null);
  };

  // Delete a comment
  const deleteComment = (id: string) => {
    setComments(comments.filter(comment => comment.id !== id));
    if (activeComment === id) {
        setActiveComment(null); // Deselect if the active comment is deleted
    }
  };

  // Add a reply to a comment
  const addReply = (commentId: string, replyText: string) => {
    if (replyText.trim()) {
      setComments(
        comments.map(comment =>
          comment.id === commentId
            ? {
                ...comment,
                replies: [
                  ...comment.replies,
                  {
                    id: Date.now().toString(),
                    text: replyText,
                    user: "Current User", // Replace with actual user info
                    timestamp: new Date()
                  }
                ]
              }
            : comment
        )
      );
    }
  };

  // Handle clicking on highlighted text
  const handleHighlightClick = (commentId: string) => {
    setActiveComment(activeComment === commentId ? null : commentId);
  };

  // Focus on comment input when selection changes
  useEffect(() => {
    if (selection && commentInputRef.current) {
      commentInputRef.current.focus();
    }
  }, [selection]);

  // Replace text with highlighted spans
  const renderHighlightedText = () => {
    if (!textRef.current) return <div ref={textRef} onMouseUp={handleTextSelection} className="relative p-4 border rounded text-gray-800 leading-relaxed whitespace-pre-wrap">{text}</div>;

    // Sort comments by start offset (descending) to avoid position shifts
    const sortedComments = [...comments].sort((a, b) =>
      b.selection.startOffset - a.selection.startOffset
    );

    let currentText = text;
    const parts: (string | JSX.Element)[] = [];
    let lastIndex = 0;

    sortedComments.forEach(comment => {
        const { startOffset, endOffset } = comment.selection;
        if (startOffset >= lastIndex && endOffset <= text.length) { // Basic validation
            // Add text before the highlight
            if (startOffset > lastIndex) {
                parts.push(currentText.substring(lastIndex, startOffset));
            }
            // Add the highlighted span
            parts.push(
                <span
                    key={comment.id}
                    className={`${activeComment === comment.id ? 'bg-yellow-300' : 'bg-yellow-100'} cursor-pointer`}
                    onClick={(e) => {
                        e.stopPropagation(); // Prevent text selection handler
                        handleHighlightClick(comment.id);
                    }}
                >
                    {currentText.substring(startOffset, endOffset)}
                </span>
            );
            lastIndex = endOffset;
        }
    });

    // Add any remaining text after the last highlight
    if (lastIndex < currentText.length) {
        parts.push(currentText.substring(lastIndex));
    }


    return <div
      ref={textRef}
      onMouseUp={handleTextSelection}
      className="relative p-4 border rounded text-gray-800 leading-relaxed whitespace-pre-wrap"
    >
        {parts.map((part, index) => <React.Fragment key={index}>{part}</React.Fragment>)}
    </div>;
  };

  // Format date to a readable string
  const formatDate = (date: Date) => {
    return new Date(date).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    });
  };

  // Handle clicks outside of comments/highlights to deselect
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (textRef.current && !textRef.current.contains(event.target as Node)) {
         // Check if click is outside the comment sidebar too if needed
         // For simplicity, deselecting on any click outside the text area for now
         // setSelection(null); // Keep selection popover open if clicked outside? Maybe not.
      }
      // More robust check needed if comment sidebar is complex
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [textRef]);


  if (isLoading) {
     return (
        <div className="flex flex-col w-full max-w-4xl mx-auto border rounded-lg shadow-lg overflow-hidden bg-white min-h-[400px]">
            <div className="flex border-b p-4 bg-gray-50">
                <h1 className="text-lg font-semibold text-gray-700">Loading Conversation...</h1>
            </div>
            <div className="flex flex-1 items-center justify-center">
                <p className="text-muted-foreground">Loading...</p>
            </div>
        </div>
     )
  }

  if (!initialText && !isLoading) {
     return (
        <div className="flex flex-col w-full max-w-4xl mx-auto border rounded-lg shadow-lg overflow-hidden bg-white min-h-[400px]">
            <div className="flex border-b p-4 bg-gray-50">
                <h1 className="text-lg font-semibold text-gray-700">Conversation</h1>
            </div>
            <div className="flex flex-1 items-center justify-center">
                <p className="text-muted-foreground">Select a trajectory to view the conversation.</p>
            </div>
        </div>
     )
  }


  return (
    // Removed outer container div, assuming parent provides structure
    <div className="flex flex-1 min-h-[400px] border rounded-lg shadow-lg overflow-hidden bg-white">
        {/* Text Area */}
        <div className="flex-1 p-4 overflow-auto relative">
          {renderHighlightedText()}

          {/* Selection comment popover */}
          {selection && (
            <div
              className="absolute flex items-center bg-white border rounded-lg shadow-lg p-2 z-10"
              style={{
                top: `${selection.position.top + 10}px`, // Offset slightly below selection
                left: `${selection.position.left}px`
              }}
              // Prevent clicks inside popover from triggering outside click handler
              onMouseDown={(e) => e.stopPropagation()}
            >
              <div className="flex items-center space-x-2">
                <input
                  ref={commentInputRef}
                  type="text"
                  value={newComment}
                  onChange={(e) => setNewComment(e.target.value)}
                  placeholder="Add a comment..."
                  className="border rounded px-2 py-1 text-sm"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      addComment();
                    }
                  }}
                />
                <button
                  onClick={addComment}
                  className="p-1 bg-blue-500 text-white rounded hover:bg-blue-600"
                  disabled={!newComment.trim()} // Disable if no text
                >
                  <Send size={16} />
                </button>
                <button
                  onClick={() => setSelection(null)}
                  className="p-1 text-gray-600 hover:text-gray-800"
                >
                  <X size={16} />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Comments sidebar */}
        <div className="w-80 border-l bg-gray-50 overflow-y-auto">
          <div className="p-4 border-b">
            <div className="flex items-center">
              <MessageSquare className="mr-2 text-gray-600" size={18} />
              <h2 className="text-md font-medium text-gray-700">Comments ({comments.length})</h2>
            </div>
          </div>

          <div className="p-4 space-y-4">
            {comments.length === 0 ? (
              <div className="text-center text-gray-500 py-8">
                <MessageSquare className="mx-auto mb-2" size={24} />
                <p>No comments yet</p>
                <p className="text-sm">Highlight text to add a comment</p>
              </div>
            ) : (
              comments.map(comment => (
                <div
                  key={comment.id}
                  className={`border rounded-lg p-3 cursor-pointer transition-all ${activeComment === comment.id ? 'bg-white shadow-md ring-2 ring-blue-300' : 'bg-gray-100 hover:bg-gray-200'}`}
                  onClick={() => handleHighlightClick(comment.id)} // Use handleHighlightClick for consistency
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center">
                      <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white mr-2">
                        <User size={16} />
                      </div>
                      <div>
                        <div className="font-medium text-sm">{comment.user}</div>
                        <div className="text-xs text-gray-500">{formatDate(comment.timestamp)}</div>
                      </div>
                    </div>

                    {/* Edit/Delete only show on hover or when active? For simplicity, always show for now */}
                    <div className="flex space-x-1">
                      <button
                        onClick={(e) => { e.stopPropagation(); setEditingComment(comment.id); }}
                        className="text-gray-500 hover:text-gray-700 p-1 rounded hover:bg-gray-300"
                      >
                        <Edit size={14} />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteComment(comment.id); }}
                        className="text-gray-500 hover:text-red-500 p-1 rounded hover:bg-gray-300"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>

                  {/* Highlighted text snippet */}
                   <blockquote className="text-xs text-gray-600 border-l-2 pl-2 italic my-1 truncate">
                     "{comment.selection.text}"
                   </blockquote>

                  <div className="mb-2">
                    {editingComment === comment.id ? (
                      <div className="mt-1">
                        <textarea
                          defaultValue={comment.text}
                          className="w-full p-2 border rounded text-sm"
                          rows={3}
                          autoFocus
                          onClick={(e) => e.stopPropagation()} // Prevent card click when editing
                          onBlur={(e) => updateComment(comment.id, e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                              e.preventDefault();
                              updateComment(comment.id, e.target.value);
                            } else if (e.key === 'Escape') {
                                setEditingComment(null); // Cancel edit on Escape
                            }
                          }}
                        />
                      </div>
                    ) : (
                      <p className="text-sm whitespace-pre-wrap">{comment.text}</p>
                    )}
                  </div>

                  {/* Replies */}
                  <div className="mt-2 pl-3 border-l-2 border-gray-200 space-y-2">
                    {comment.replies.map((reply: any) => ( // Add type for reply if defined
                      <div key={reply.id} className="text-xs py-1">
                        <div className="flex items-center mb-1">
                           <div className="w-5 h-5 rounded-full bg-gray-400 flex items-center justify-center text-white mr-1.5">
                             <User size={10} />
                           </div>
                          <div className="font-medium mr-1">{reply.user}</div>
                          <div className="text-gray-500">{formatDate(reply.timestamp)}</div>
                        </div>
                        <p className="pl-6">{reply.text}</p> {/* Indent reply text */}
                      </div>
                    ))}

                    {/* Reply Input - Show only when comment is active */}
                    {activeComment === comment.id && (
                      <div className="flex items-center mt-2 pt-2 border-t border-gray-200">
                        <input
                          type="text"
                          placeholder="Reply..."
                          className="flex-1 border rounded-l px-2 py-1 text-xs"
                          onClick={(e) => e.stopPropagation()} // Prevent card click
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && (e.target as HTMLInputElement).value.trim()) {
                              addReply(comment.id, (e.target as HTMLInputElement).value);
                              (e.target as HTMLInputElement).value = ''; // Clear input
                            }
                          }}
                        />
                        <button
                          className="bg-blue-500 text-white rounded-r p-1 text-xs hover:bg-blue-600"
                          onClick={(e) => {
                            e.stopPropagation(); // Prevent card click
                            const input = (e.target as HTMLElement).closest('div')?.querySelector('input');
                            if (input && input.value.trim()) {
                                addReply(comment.id, input.value);
                                input.value = ''; // Clear input
                            }
                          }}
                        >
                          Reply
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
  );
};

export default CommentSystem;