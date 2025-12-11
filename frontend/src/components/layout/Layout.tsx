import { ReactNode } from 'react';
import Header from './Header';

interface LayoutProps {
  children: ReactNode;
  onNewConversation?: () => void;
}

/**
 * Main layout component with responsive design
 * Provides consistent structure across the application
 * Requirements: 5.1, 5.2, 9.1
 */
export default function Layout({ children, onNewConversation }: LayoutProps) {
  return (
    <div className="min-h-screen bg-background" lang="en">
      <Header onNewConversation={onNewConversation} />
      <main 
        className="h-[calc(100vh-4rem)]"
        role="main"
        aria-label="Main content"
      >
        {children}
      </main>
    </div>
  );
}
