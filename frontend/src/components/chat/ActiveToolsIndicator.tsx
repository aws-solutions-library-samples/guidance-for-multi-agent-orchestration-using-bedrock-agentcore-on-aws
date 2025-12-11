import { Wrench, Package, User, HelpCircle, Loader2 } from 'lucide-react';

interface ActiveToolsIndicatorProps {
  tools: string[];
}

const toolConfig: Record<string, { icon: typeof Wrench; label: string; color: string }> = {
  'order-management': {
    icon: Package,
    label: 'Order Management',
    color: 'bg-green-100 text-green-700 border-green-300',
  },
  'personalization': {
    icon: User,
    label: 'Personalization',
    color: 'bg-purple-100 text-purple-700 border-purple-300',
  },
  'product-recommendation': {
    icon: Package,
    label: 'Product Recommendations',
    color: 'bg-blue-100 text-blue-700 border-blue-300',
  },
  'troubleshooting': {
    icon: Wrench,
    label: 'Troubleshooting',
    color: 'bg-orange-100 text-orange-700 border-orange-300',
  },
};

export default function ActiveToolsIndicator({ tools }: ActiveToolsIndicatorProps) {
  if (tools.length === 0) {
    return null;
  }

  return (
    <div 
      className="px-4 py-2 bg-gray-50 border-t border-gray-200"
      role="status"
      aria-live="polite"
      aria-label="Consulting specialized agents"
    >
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center gap-2 flex-wrap">
          <Loader2 
            className="w-4 h-4 animate-spin text-blue-600" 
            aria-hidden="true"
          />
          <span className="text-sm text-gray-600 font-medium">
            Consulting other agents:
          </span>
          <div className="flex flex-wrap gap-2" role="list">
            {tools.map((tool, index) => {
              const config = toolConfig[tool] || {
                icon: HelpCircle,
                label: tool,
                color: 'bg-gray-100 text-gray-700 border-gray-300',
              };
              const Icon = config.icon;

              return (
                <div
                  key={`${tool}-${index}`}
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${config.color} animate-pulse`}
                  role="listitem"
                  aria-label={`Consulting ${config.label} agent`}
                >
                  <Icon className="w-3.5 h-3.5" aria-hidden="true" />
                  <span>{config.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
