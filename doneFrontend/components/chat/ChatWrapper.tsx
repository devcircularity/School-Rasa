// components/chat/ChatWrapper.tsx - Complete version with academic status refresh
'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { chatService } from '@/services/chats'
import ChatInput from './ChatInput'
import ChatMessages from './ChatMessages'
import { Action } from './tools/types'

interface ChatWrapperProps {
  conversationId?: string;
  initialMessages?: any[];
  onConversationCreated?: (conversationId: string) => void;
  onConversationUpdated?: (conversationId: string) => void;
  className?: string;
  initialMessage?: string | null;
  initialContext?: any;
  placeholder?: string;
}

/**
 * Helper function to dispatch academic status update event
 * This triggers the AcademicStatusBar to refresh
 */
const dispatchAcademicStatusUpdate = () => {
  console.log('ChatWrapper: Dispatching academic status update event')
  window.dispatchEvent(new CustomEvent('academic-status-updated'))
}

/**
 * ChatWrapper provides a complete chat interface using the RESTful message flow.
 * It handles both regular text messages and file attachments seamlessly.
 */
export default function ChatWrapper({ 
  conversationId,
  initialMessages = [],
  onConversationCreated,
  onConversationUpdated,
  className,
  initialMessage = null,
  initialContext = null,
  placeholder
}: ChatWrapperProps) {
  const router = useRouter()
  const [messages, setMessages] = useState(initialMessages)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // Use ref to track if initial message was already processed
  const initialMessageProcessed = useRef(false)

  // Process initial message when component mounts
  useEffect(() => {
    // Check ref instead of state to prevent React strict mode double-firing
    if (initialMessage && !initialMessageProcessed.current && !busy) {
      console.log('ChatWrapper: Processing initial message:', initialMessage)
      initialMessageProcessed.current = true
      handleSendMessage(initialMessage, initialContext)
    }
  }, [initialMessage])

  // Handle regular text messages using RESTful endpoints
  const handleSendMessage = useCallback(async (text: string, context?: any) => {
    if (busy) {
      console.log('ChatWrapper: Busy, ignoring send request')
      return
    }
    
    console.log('ChatWrapper: Sending message:', text)
    setBusy(true)
    setError(null)
    
    // Add user message optimistically
    const userMessage = { role: 'user' as const, content: text }
    setMessages(prev => [...prev, userMessage])

    try {
      console.log('ChatWrapper: Sending message', { text, conversationId, context })
      
      // Use the RESTful chat service
      const response = await chatService.sendMessage(text, conversationId, context)
      
      console.log('ChatWrapper: Message response', {
        conversation_id: response.conversation_id,
        message_id: response.message_id,
        intent: response.intent
      })
      
      // Add assistant response
      const assistantMessage = {
        role: 'assistant' as const,
        content: response.response,
        blocks: response.blocks,
        id: response.message_id,
        intent: response.intent
      }
      setMessages(prev => [...prev, assistantMessage])

      // Handle new conversation creation
      if (!conversationId && response.conversation_id) {
        console.log('ChatWrapper: New conversation created', response.conversation_id)
        onConversationCreated?.(response.conversation_id)
        
        // If we're on a "new" chat page, redirect to the actual conversation
        if (window.location.pathname.includes('/chat/new')) {
          router.replace(`/chat/${response.conversation_id}`)
        }
      }

      // Notify parent of updates
      if (response.conversation_id) {
        onConversationUpdated?.(response.conversation_id)
      }

      // Trigger academic status refresh after successful message
      // This ensures the status bar updates when users create/modify academic data
      dispatchAcademicStatusUpdate()

    } catch (error: any) {
      console.error('ChatWrapper: Failed to send message:', error)
      
      // Remove optimistic message
      setMessages(prev => prev.slice(0, -1))
      
      // Add error message
      const errorMessage = {
        role: 'assistant' as const,
        content: 'Sorry, I encountered an error processing your message. Please try again.'
      }
      setMessages(prev => [...prev, errorMessage])
      
      setError(error.message || 'Failed to send message')
    } finally {
      setBusy(false)
    }
  }, [busy, conversationId, router, onConversationCreated, onConversationUpdated])

  // Handle messages with file attachments using RESTful endpoints
  const handleSendWithFiles = useCallback(async (
    message: string, 
    files: File[], 
    providedConversationId?: string
  ) => {
    if (busy) return
    setBusy(true)
    setError(null)
    
    // Add user message optimistically
    const userMessage = { role: 'user' as const, content: message }
    setMessages(prev => [...prev, userMessage])

    try {
      const targetConversationId = providedConversationId || conversationId
      
      console.log('ChatWrapper: Sending message with files', {
        message,
        filesCount: files.length,
        conversationId: targetConversationId
      })
      
      // Use the RESTful chat service for file uploads
      const response = await chatService.sendMessageWithFiles(
        message, 
        files, 
        targetConversationId
      )
      
      console.log('ChatWrapper: File message response', {
        conversation_id: response.conversation_id,
        message_id: response.message_id,
        attachment_processed: response.attachment_processed
      })
      
      // Add assistant response
      const assistantMessage = {
        role: 'assistant' as const,
        content: response.response,
        blocks: response.blocks,
        id: response.message_id,
        intent: response.intent
      }
      setMessages(prev => [...prev, assistantMessage])

      // Handle new conversation creation
      if (!conversationId && response.conversation_id) {
        console.log('ChatWrapper: New conversation created with files', response.conversation_id)
        onConversationCreated?.(response.conversation_id)
        
        if (window.location.pathname.includes('/chat/new')) {
          router.replace(`/chat/${response.conversation_id}`)
        }
      }

      // Notify parent of updates
      if (response.conversation_id) {
        onConversationUpdated?.(response.conversation_id)
      }

      // Trigger academic status refresh after successful file message
      dispatchAcademicStatusUpdate()

    } catch (error: any) {
      console.error('ChatWrapper: Failed to send message with files:', error)
      
      // Remove optimistic message
      setMessages(prev => prev.slice(0, -1))
      
      // Add error message
      const errorMessage = {
        role: 'assistant' as const,
        content: 'Sorry, I encountered an error processing your files. Please try again.'
      }
      setMessages(prev => [...prev, errorMessage])
      
      setError(error.message || 'Failed to process files')
    } finally {
      setBusy(false)
    }
  }, [busy, conversationId, router, onConversationCreated, onConversationUpdated])

  // Handle block actions (buttons, links, etc. in assistant responses)
  const handleBlockAction = useCallback(async (action: Action) => {
    console.log('ChatWrapper: Block action triggered', action)
    
    switch (action.type) {
      case 'query':
        if (action.payload && 'message' in action.payload) {
          await handleSendMessage(action.payload.message)
        }
        break
      
      case 'route':
        if (action.target) {
          const [section, view] = action.target.split(':')
          router.push(`/${section}${view ? `/${view}` : ''}`)
        }
        break
      
      case 'download':
        if (action.endpoint) {
          window.open(action.endpoint, '_blank')
        }
        break
      
      case 'mutation':
        if (action.endpoint) {
          try {
            const response = await fetch(action.endpoint, {
              method: action.method || 'POST',
              headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`,
                'X-School-ID': localStorage.getItem('schoolId') || ''
              },
              body: action.payload ? JSON.stringify(action.payload) : undefined
            })
            
            if (!response.ok) {
              throw new Error(`HTTP ${response.status}`)
            }
            
            console.log('ChatWrapper: Mutation successful')
            
            // Trigger academic status refresh after mutations
            dispatchAcademicStatusUpdate()
          } catch (error) {
            console.error('ChatWrapper: Mutation failed:', error)
          }
        }
        break
      
      default:
        console.warn('ChatWrapper: Unhandled action type:', action.type)
    }
  }, [handleSendMessage, router])

  // Show only input if no messages yet
  const showOnlyInput = messages.length === 0 && !initialMessage

  if (showOnlyInput) {
    return (
      <div className={`${className || ''}`}>
        {/* Error display */}
        {error && (
          <div className="mx-4 mb-3 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <div className="text-sm text-red-600 dark:text-red-400">
              <div className="font-medium">Error</div>
              <div className="mt-1">{error}</div>
            </div>
            <button 
              onClick={() => setError(null)}
              className="mt-2 text-xs text-red-500 hover:text-red-700 underline"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Just the input */}
        <ChatInput
          onSend={handleSendMessage}
          onSendWithFiles={handleSendWithFiles}
          busy={busy}
          conversationId={conversationId}
          placeholder={placeholder}
        />
      </div>
    )
  }

  return (
    <div className={`h-full flex flex-col ${className || ''}`}>
      {/* Error display */}
      {error && (
        <div className="mx-4 mb-3 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <div className="text-sm text-red-600 dark:text-red-400">
            <div className="font-medium">Error</div>
            <div className="mt-1">{error}</div>
          </div>
          <button 
            onClick={() => setError(null)}
            className="mt-2 text-xs text-red-500 hover:text-red-700 underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Messages area */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <ChatMessages 
          messages={messages} 
          isLoading={busy} 
          onAction={handleBlockAction}
          conversationId={conversationId}
        />
      </div>

      {/* Input area */}
      <div className="flex-none">
        <ChatInput
          onSend={handleSendMessage}
          onSendWithFiles={handleSendWithFiles}
          busy={busy}
          conversationId={conversationId}
          placeholder={placeholder}
        />
      </div>
    </div>
  )
}