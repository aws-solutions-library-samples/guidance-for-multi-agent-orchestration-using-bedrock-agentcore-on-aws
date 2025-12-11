import { useAuth } from './hooks/useAuth';
import { LoginForm } from './components/auth/LoginForm';
import { Layout } from './components/layout';
import ChatInterface from './components/chat/ChatInterface';
import { ChatProvider, useChatContext } from './contexts/ChatContext';

/**
 * Main App component with authentication
 */
function App() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginForm onSuccess={() => window.location.reload()} />;
  }

  return (
    <>
      {/* Skip to main content link for keyboard navigation */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-primary focus:text-primary-foreground focus:rounded-md focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
      >
        Skip to main content
      </a>
      <ChatProvider>
        <AuthenticatedApp />
      </ChatProvider>
    </>
  );
}

/**
 * Authenticated application content
 */
function AuthenticatedApp() {
  const { isLoading } = useAuth();
  
  // Access chat context to provide startNewConversation to Header
  const { startNewConversation } = useChatContext();

  if (isLoading) {
    return (
      <div 
        className="min-h-screen bg-background flex items-center justify-center"
        role="status"
        aria-live="polite"
        aria-label="Loading application"
      >
        <div className="text-center">
          <div 
            className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-current border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]" 
            role="status"
            aria-label="Loading spinner"
          >
            <span className="!absolute !-m-px !h-px !w-px !overflow-hidden !whitespace-nowrap !border-0 !p-0 ![clip:rect(0,0,0,0)]">
              Loading...
            </span>
          </div>
          <p className="mt-4 text-muted-foreground">Loading application...</p>
        </div>
      </div>
    );
  }

  return (
    <Layout onNewConversation={startNewConversation}>
      <div id="main-content">
        <ChatInterface />
      </div>
    </Layout>
  );
}

export default App;
