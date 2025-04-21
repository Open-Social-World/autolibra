import React, { useState, useRef, useEffect } from 'react';
import { User, MessageSquare, X, Send, Trash2, Edit } from 'lucide-react';

interface CommentSystemProps {
  initialText: string;
  isLoading?: boolean;
}

const CommentSystem: React.FC<CommentSystemProps> = ({ initialText, isLoading = false }) => {
  const [text, setText] = useState(initialText);
  const [selection, setSelection] = useState<any>(null);
  const [comments, setComments] = useState<any[]>([]);
  const [activeComment, setActiveComment] = useState<string | null>(null);
  const [newComment, setNewComment] = useState('');
  const [editingComment, setEditingComment] = useState<string | null>(null);
  const textRef = useRef<HTMLDivElement>(null);
  const commentInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setText(initialText);
    setComments([]);
    setSelection(null);
    setActiveComment(null);
    setNewComment('');
    setEditingComment(null);
  }, [initialText]);

  const handleTextSelection = () => {
    const selectionObj = window.getSelection();

    if (
        selectionObj &&
        selectionObj.rangeCount > 0 &&
        selectionObj.toString().length > 0 &&
        textRef.current?.contains(selectionObj.anchorNode)
    ) {
        const range = selectionObj.getRangeAt(0);
        const selectedText = range.toString();

        const preSelectionRange = document.createRange();
        preSelectionRange.selectNodeContents(textRef.current);
        preSelectionRange.setEnd(range.startContainer, range.startOffset);
        const startOffset = preSelectionRange.toString().length;
        const endOffset = startOffset + selectedText.length;

        const rect = range.getBoundingClientRect();
        const textRect = textRef.current.getBoundingClientRect();

        setSelection({
            text: selectedText,
            startOffset: startOffset,
            endOffset: endOffset,
            position: {
                left: rect.right - textRect.left,
                top: rect.top - textRect.top
            }
        });
    } else {
        setSelection(null);
    }
  };

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
        user: "Current User",
        timestamp: new Date(),
        replies: []
      };

      setComments([...comments, comment]);
      setNewComment('');
      setSelection(null);
      setActiveComment(comment.id);
    }
  };

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

  const deleteComment = (id: string) => {
    setComments(comments.filter(comment => comment.id !== id));
    if (activeComment === id) {
        setActiveComment(null);
    }
  };

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
                    user: "Current User",
                    timestamp: new Date()
                  }
                ]
              }
            : comment
        )
      );
    }
  };

  const handleHighlightClick = (commentId: string) => {
    setActiveComment(activeComment === commentId ? null : commentId);
  };

  useEffect(() => {
    if (selection && commentInputRef.current) {
      commentInputRef.current.focus();
    }
  }, [selection]);

  const renderHighlightedText = () => {
    const sourceText = initialText;
    if (!sourceText) return <div ref={textRef} onMouseUp={handleTextSelection} className="relative p-4 border rounded text-gray-800 leading-relaxed whitespace-pre-wrap"></div>;

    const sortedComments = [...comments].sort((a, b) =>
      a.selection.startOffset - b.selection.startOffset
    );

    const parts: (string | JSX.Element)[] = [];
    let currentIndex = 0;

    sortedComments.forEach(comment => {
      const { startOffset, endOffset } = comment.selection;

      if (startOffset >= currentIndex && endOffset >= startOffset && endOffset <= sourceText.length) {
        if (startOffset > currentIndex) {
          parts.push(sourceText.substring(currentIndex, startOffset));
        }

        parts.push(
          <span
            key={comment.id}
            className={`${activeComment === comment.id ? 'bg-[#8aa88a]' : 'bg-[#a7c9a7]'} cursor-pointer`}
            onClick={(e) => {
              e.stopPropagation();
              handleHighlightClick(comment.id);
            }}
          >
            {sourceText.substring(startOffset, endOffset)}
          </span>
        );

        currentIndex = endOffset;
      }
    });

    if (currentIndex < sourceText.length) {
      parts.push(sourceText.substring(currentIndex));
    }

    return (
      <div
        ref={textRef}
        onMouseUp={handleTextSelection}
        className="relative p-4 border rounded text-gray-800 leading-relaxed whitespace-pre-wrap"
      >
        {parts.map((part, index) => (
          <React.Fragment key={index}>{part}</React.Fragment>
        ))}
      </div>
    );
  };

  const formatDate = (date: Date) => {
    return new Date(date).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    });
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      // ... (implementation)
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [textRef]);

  if (isLoading) {
     return (
        <div className="flex flex-col w-full max-w-4xl mx-auto border rounded-lg shadow-lg overflow-hidden bg-white min-h-[400px]">
            {/* ... loading content ... */}
        </div>
     )
  }

  if (!initialText && !isLoading) {
     return (
        <div className="flex flex-col w-full max-w-4xl mx-auto border rounded-lg shadow-lg overflow-hidden bg-white min-h-[400px]">
             {/* ... empty content ... */}
        </div>
     )
  }

  return (
    <div className="flex flex-1 min-h-[400px] border rounded-lg shadow-lg overflow-hidden bg-white">
        <div className="flex-1 p-4 overflow-auto relative">
          {renderHighlightedText()}

          {selection && (
            <div
              className="absolute flex items-center bg-white border rounded-lg shadow-lg p-2 z-10"
              style={{
                top: `${selection.position.top + 10}px`,
                left: `${selection.position.left}px`
              }}
              onMouseDown={(e) => e.stopPropagation()}
            >
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
                  disabled={!newComment.trim()}
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
          )}
        </div>

        <div className="w-80 border-l bg-gray-50 overflow-y-auto">
          <div className="p-4 border-b">
             <h2 className="text-md font-medium text-gray-700">Comments ({comments.length})</h2>
          </div>

          <div className="p-4 space-y-4">
            {comments.length === 0 ? (
               {/* ... no comments message ... */}
            ) : (
              comments.map(comment => (
                <div
                  key={comment.id}
                  className={`border rounded-lg p-3 cursor-pointer transition-all ${activeComment === comment.id ? 'bg-white shadow-md ring-2 ring-blue-300' : 'bg-gray-100 hover:bg-gray-200'}`}
                  onClick={() => handleHighlightClick(comment.id)}
                >
                   <button
                        onClick={(e) => { e.stopPropagation(); setEditingComment(comment.id); }}
                      >
                        <Edit size={14} />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteComment(comment.id); }}
                      >
                        <Trash2 size={14} />
                      </button>
                   {editingComment === comment.id ? (
                      <div className="mt-1">
                        <textarea
                          defaultValue={comment.text}
                          onBlur={(e) => updateComment(comment.id, e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                              e.preventDefault();
                              updateComment(comment.id, e.target.value);
                            } else if (e.key === 'Escape') {
                                setEditingComment(null);
                            }
                          }}
                        />
                      </div>
                    ) : (
                      <p className="text-sm whitespace-pre-wrap">{comment.text}</p>
                    )}
                   {activeComment === comment.id && (
                      <div className="flex items-center mt-2 pt-2 border-t border-gray-200">
                        <input
                          type="text"
                          placeholder="Reply..."
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && (e.target as HTMLInputElement).value.trim()) {
                              addReply(comment.id, (e.target as HTMLInputElement).value);
                              (e.target as HTMLInputElement).value = '';
                            }
                          }}
                        />
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            const input = (e.target as HTMLElement).closest('div')?.querySelector('input');
                            if (input && input.value.trim()) {
                                addReply(comment.id, input.value);
                                input.value = '';
                            }
                          }}
                        >
                          Reply
                        </button>
                      </div>
                    )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
  );
};

export default CommentSystem; 