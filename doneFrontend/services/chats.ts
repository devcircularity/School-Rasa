// services/chats.ts - Updated to use proper RESTful message endpoints

import { api } from './api'
import { chatEventBus, getCurrentUserId } from '@/utils/chatEventBus'
import { Block } from '@/components/chat/tools/types'

// Updated types to match backend EXACTLY
export type ChatMessage = {
  message: string
  context?: Record<string, any>
  attachments?: FileAttachment[]
}

export type FileAttachment = {
  attachment_id: string
  original_filename: string
  content_type: string
  file_size: number
  cloudinary_url: string
  cloudinary_public_id: string
  upload_timestamp: string
  ocr_processed: boolean
  ocr_data?: any
}

export type ChatResponse = {
  response: string
  intent?: string
  data?: Record<string, any>
  action_taken?: string
  suggestions?: string[]
  conversation_id?: string
  message_id?: string
  blocks?: Block[]
  attachment_processed?: boolean
}

export type Conversation = {
  id: string
  title: string
  first_message: string
  last_activity: string
  message_count: number
  is_archived: boolean
  created_at: string
}

export type Message = {
  id: string
  conversation_id: string
  message_type: 'USER' | 'ASSISTANT'
  content: string
  intent?: string
  context_data?: Record<string, any>
  response_data?: Record<string, any>
  processing_time_ms?: number
  created_at: string
  rating?: number | null
  rated_at?: string | null
}

export type ConversationDetail = {
  id: string
  title: string
  first_message: string
  last_activity: string
  message_count: number
  is_archived: boolean
  created_at: string
  messages: Message[]
}

export type DisplayMessage = {
  role: 'user' | 'assistant'
  content: string
  blocks?: Block[]
  response_data?: Record<string, any>
  intent?: string
  id?: string
  timestamp?: string
  rating?: number | null
}

// Message transformation utility with complete data preservation
export const transformMessagesToDisplay = (messages: Message[]): DisplayMessage[] => {
  return messages.map((msg) => {
    const role: 'user' | 'assistant' = msg.message_type === 'USER' ? 'user' : 'assistant'
    
    const displayMessage: DisplayMessage = {
      role,
      content: msg.content,
      blocks: role === 'assistant' && msg.response_data?.blocks ? msg.response_data.blocks : undefined,
      response_data: msg.response_data,
      intent: msg.intent,
      id: msg.id,
      timestamp: msg.created_at,
      rating: msg.rating
    }
    
    return displayMessage;
  })
}

export type ConversationList = {
  conversations: Conversation[]
  total: number
  page: number
  limit: number
  has_next: boolean
}

export const chatService = {
  // Create a new conversation
  async createConversation(title: string, firstMessage: string): Promise<Conversation> {
    const userId = getCurrentUserId() ?? undefined
    
    try {
      const { data } = await api.post('/api/chat/conversations', {
        title,
        first_message: firstMessage
      })
      
      // Broadcast event for real-time sync
      chatEventBus.conversationCreated(data.id, data, userId)
      
      return data
    } catch (error) {
      console.error('Failed to create conversation:', error)
      throw error
    }
  },

  // Send a message to a specific conversation using the RESTful endpoint
  // services/chats.ts - Updated timeout for AI requests

  // Send a message to a specific conversation using the RESTful endpoint
  async sendMessageToConversation(
    conversationId: string, 
    message: string, 
    context?: Record<string, any>,
    attachments?: FileAttachment[]
  ): Promise<ChatResponse> {
    const userId = getCurrentUserId() ?? undefined
    
    console.log('=== SENDING MESSAGE TO CONVERSATION ===')
    console.log('ConversationId:', conversationId)
    console.log('Message:', message)
    console.log('Attachments:', attachments?.length || 0)
    
    try {
      const { data } = await api.post(`/api/chat/conversations/${conversationId}/messages`, {
        message,
        context,
        attachments
      } as ChatMessage, {
        timeout: 60000  // ✅ INCREASED from 20000 to 60000 (60 seconds for AI processing)
      })
      
      console.log('Message sent response:', {
        conversation_id: data.conversation_id,
        message_id: data.message_id,
        intent: data.intent,
        response_preview: data.response?.substring(0, 100)
      })
      
      // Broadcast event for real-time sync
      chatEventBus.messageSent(conversationId, { message, response: data.response }, userId)
      
      return data
    } catch (error) {
      console.error('Failed to send message to conversation:', error)
      throw error
    }
  },

  // Send message with files - handles both new and existing conversations
  async sendMessageWithFiles(
    message: string, 
    files: File[], 
    conversationId?: string
  ): Promise<ChatResponse> {
    const userId = getCurrentUserId() ?? undefined
    
    console.log('=== SEND MESSAGE WITH FILES ===')
    console.log('Message:', message)
    console.log('Files count:', files.length)
    console.log('ConversationId:', conversationId)
    
    // For new conversations, create one first
    if (!conversationId || conversationId === 'new') {
      console.log('Creating new conversation for files')
      
      // Create conversation
      const newConversation = await this.createConversation(
        message.slice(0, 50) + (message.length > 50 ? '...' : ''),
        message
      )
      
      conversationId = newConversation.id
      console.log('New conversation created:', conversationId)
    }
    
    const formData = new FormData()
    formData.append('message', message)
    
    // Append files
    files.forEach((file) => {
      formData.append('files', file)
    })

    try {
      console.log('Sending files to conversation:', conversationId)
      const { data } = await api.post(`/api/chat/conversations/${conversationId}/messages`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 120000, // 2 minutes timeout for file processing
      })
      
      console.log('File message response:', {
        conversation_id: data.conversation_id,
        message_id: data.message_id,
        intent: data.intent,
        attachment_processed: data.attachment_processed
      })
      
      // Broadcast event
      chatEventBus.messageSent(conversationId!, { message, response: data.response }, userId)
      
      return data
    } catch (error: any) {
      console.error('Failed to send message with files:', error)
      throw new Error(error.response?.data?.detail || error.message || 'File processing failed')
    }
  },

  // Rate a message
  async rateMessage(conversationId: string, messageId: string, rating: 1 | -1 | null): Promise<void> {
    try {
      await api.post(`/api/chat/conversations/${conversationId}/messages/${messageId}/rate`, {
        rating
      })
    } catch (error) {
      console.error('Failed to rate message:', error)
      throw error
    }
  },

  // Get list of conversations with pagination
  async getConversations(page = 1, limit = 20, archived?: boolean): Promise<ConversationList> {
    try {
      const { data } = await api.get('/api/chat/conversations', {
        params: { page, limit, archived }
      })
      return data
    } catch (error) {
      console.error('Failed to get conversations:', error)
      throw error
    }
  },

  // Get conversation with all messages and proper transformation
  async getConversation(conversationId: string): Promise<ConversationDetail & { displayMessages: DisplayMessage[] }> {
    try {
      console.log('=== GETTING CONVERSATION ===', conversationId)
      
      const { data } = await api.get(`/api/chat/conversations/${conversationId}`)
      
      console.log('Raw conversation data:', {
        id: data.id,
        title: data.title,
        messageCount: data.messages?.length || 0
      })
      
      // Transform the messages to the display format with complete data preservation
      const displayMessages = transformMessagesToDisplay(data.messages || [])
      
      return {
        ...data,
        displayMessages
      }
    } catch (error) {
      console.error('Failed to get conversation:', error)
      throw error
    }
  },

  // Update conversation (rename, archive)
  async updateConversation(conversationId: string, updates: { title?: string; is_archived?: boolean }): Promise<Conversation> {
    const userId = getCurrentUserId() ?? undefined
    
    try {
      await api.put(`/api/chat/conversations/${conversationId}`, updates)
      
      // Get updated conversation
      const { data } = await api.get(`/api/chat/conversations/${conversationId}`, {
        params: { include_messages: false }
      })
      
      // Broadcast update event
      chatEventBus.conversationUpdated(conversationId, updates, userId)
      
      return data
    } catch (error) {
      console.error('Failed to update conversation:', error)
      throw error
    }
  },

  // Delete conversation
  async deleteConversation(conversationId: string): Promise<void> {
    const userId = getCurrentUserId() ?? undefined
    
    try {
      await api.delete(`/api/chat/conversations/${conversationId}`)
      
      // Broadcast delete event
      chatEventBus.conversationDeleted(conversationId, userId)
    } catch (error) {
      console.error('Failed to delete conversation:', error)
      throw error
    }
  },

  // Upload file for chat
  async uploadFile(file: File): Promise<FileAttachment> {
    try {
      const formData = new FormData()
      formData.append('file', file)
      
      const { data } = await api.post('/api/chat/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })
      
      return data
    } catch (error) {
      console.error('Failed to upload file:', error)
      throw error
    }
  },

  // Health check
  async healthCheck(): Promise<{ status: string; rasa_connected: boolean; timestamp: number }> {
    try {
      const { data } = await api.get('/api/chat/health')
      return data
    } catch (error) {
      console.error('Health check failed:', error)
      throw error
    }
  },

  // Force refresh of chat data
  forceRefresh(): void {
    const userId = getCurrentUserId() ?? undefined
    chatEventBus.forceRefresh(userId)
  },

  // Legacy compatibility - send message (creates conversation if needed)
  async sendMessage(message: string, conversationId?: string, context?: Record<string, any>): Promise<ChatResponse> {
    // If no conversation ID, create a new conversation first
    if (!conversationId || conversationId === 'new') {
      const newConversation = await this.createConversation(
        message.slice(0, 50) + (message.length > 50 ? '...' : ''),
        message
      )
      conversationId = newConversation.id
    }
    
    return this.sendMessageToConversation(conversationId, message, context)
  }
}