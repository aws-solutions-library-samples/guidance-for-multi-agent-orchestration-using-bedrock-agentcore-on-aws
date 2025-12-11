import { useAuth } from '@/hooks/useAuth';
import { LogOut, Menu, X, MessageSquarePlus } from 'lucide-react';
import { useState } from 'react';

/**
 * Header component with app title, new conversation button, and logout button
 * Responsive design with mobile menu
 * Requirements: 5.1, 5.2, 9.1
 */
interface HeaderProps {
  onNewConversation?: () => void;
}

export default function Header({ onNewConversation }: HeaderProps) {
  const { user, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const toggleMobileMenu = () => {
    setMobileMenuOpen(!mobileMenuOpen);
  };

  return (
    <header 
      className="sticky top-0 z-50 w-full border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60"
      role="banner"
    >
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          {/* Logo and Title */}
          <div className="flex items-center gap-3">
            <div 
              className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground"
              aria-hidden="true"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-6 w-6"
                aria-hidden="true"
              >
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </div>
            <div className="hidden sm:block">
              <h1 className="text-lg font-semibold text-foreground">
                Customer Support Assistant
              </h1>
            </div>
            <div className="sm:hidden">
              <h1 className="text-base font-semibold text-foreground">
                Support
              </h1>
            </div>
          </div>

          {/* Desktop Navigation */}
          <nav 
            className="hidden md:flex items-center gap-4"
            aria-label="User navigation"
          >
            {user && (
              <div 
                className="flex items-center gap-2 text-sm text-muted-foreground"
                role="status"
                aria-label={`Logged in as ${user.email}`}
              >
                <div 
                  className="flex h-8 w-8 items-center justify-center rounded-full bg-muted"
                  aria-hidden="true"
                >
                  <span className="text-xs font-medium">
                    {user.email.charAt(0).toUpperCase()}
                  </span>
                </div>
                <span className="max-w-[200px] truncate">{user.email}</span>
              </div>
            )}
            {onNewConversation && (
              <button
                onClick={onNewConversation}
                className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                aria-label="Start a new conversation"
              >
                <MessageSquarePlus className="h-4 w-4" aria-hidden="true" />
                <span>New Conversation</span>
              </button>
            )}
            <button
              onClick={logout}
              className="inline-flex items-center gap-2 rounded-md bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground transition-colors hover:bg-destructive/90 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              aria-label="Logout from application"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              <span>Logout</span>
            </button>
          </nav>

          {/* Mobile Menu Button */}
          <button
            onClick={toggleMobileMenu}
            className="md:hidden inline-flex items-center justify-center rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
            aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={mobileMenuOpen}
            aria-controls="mobile-menu"
          >
            {mobileMenuOpen ? (
              <X className="h-6 w-6" aria-hidden="true" />
            ) : (
              <Menu className="h-6 w-6" aria-hidden="true" />
            )}
          </button>
        </div>

        {/* Mobile Navigation */}
        {mobileMenuOpen && (
          <nav 
            id="mobile-menu"
            className="md:hidden border-t border-border py-4"
            aria-label="Mobile navigation"
          >
            <div className="space-y-4">
              {user && (
                <div 
                  className="flex items-center gap-3 px-2 py-2"
                  role="status"
                  aria-label={`Logged in as ${user.email}`}
                >
                  <div 
                    className="flex h-10 w-10 items-center justify-center rounded-full bg-muted"
                    aria-hidden="true"
                  >
                    <span className="text-sm font-medium">
                      {user.email.charAt(0).toUpperCase()}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">
                      {user.email}
                    </p>
                    {user.customerId && (
                      <p className="text-xs text-muted-foreground truncate">
                        ID: {user.customerId}
                      </p>
                    )}
                  </div>
                </div>
              )}
              {onNewConversation && (
                <button
                  onClick={() => {
                    onNewConversation();
                    setMobileMenuOpen(false);
                  }}
                  className="w-full inline-flex items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                  aria-label="Start a new conversation"
                >
                  <MessageSquarePlus className="h-4 w-4" aria-hidden="true" />
                  <span>New Conversation</span>
                </button>
              )}
              <button
                onClick={() => {
                  logout();
                  setMobileMenuOpen(false);
                }}
                className="w-full inline-flex items-center justify-center gap-2 rounded-md bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground transition-colors hover:bg-destructive/90 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                aria-label="Logout from application"
              >
                <LogOut className="h-4 w-4" aria-hidden="true" />
                <span>Logout</span>
              </button>
            </div>
          </nav>
        )}
      </div>
    </header>
  );
}
