import { Wrench, Package, User, HelpCircle } from 'lucide-react';

interface ToolIndicatorProps {
  tools: string[];
}

const toolIcons: Record<string, { icon: typeof Wrench; label: string; color: string }> = {
  'order-management': {
    icon: Package,
    label: 'Order Management',
    color: 'bg-green-100 text-green-700 border-green-200',
  },
  'personalization': {
    icon: User,
    label: 'Personalization',
    color: 'bg-purple-100 text-purple-700 border-purple-200',
  },
  'product-recommendation': {
    icon: Package,
    label: 'Product Recommendations',
    color: 'bg-blue-100 text-blue-700 border-blue-200',
  },
  'troubleshooting': {
    icon: Wrench,
    label: 'Troubleshooting',
    color: 'bg-orange-100 text-orange-700 border-orange-200',
  },
};

export default function ToolIndicator({ tools }: ToolIndicatorProps) {
  return (
    <div 
      className="flex flex-wrap gap-2"
      role="list"
      aria-label="Specialized agents consulted"
    >
      {tools.map((tool, index) => {
        const toolConfig = toolIcons[tool] || {
          icon: HelpCircle,
          label: tool,
          color: 'bg-gray-100 text-gray-700 border-gray-200',
        };
        const Icon = toolConfig.icon;

        return (
          <div
            key={`${tool}-${index}`}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${toolConfig.color}`}
            role="listitem"
            aria-label={`Used ${toolConfig.label} agent`}
          >
            <Icon className="w-3.5 h-3.5" aria-hidden="true" />
            <span>{toolConfig.label}</span>
          </div>
        );
      })}
    </div>
  );
}
