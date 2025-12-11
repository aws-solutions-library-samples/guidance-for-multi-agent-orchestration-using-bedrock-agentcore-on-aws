#!/usr/bin/env python3
"""
Show agent conversation flow and memory context from CloudWatch logs.

Fetches logs from AgentCore runtimes and displays agent interactions in a readable format:
- Agent reasoning and responses
- Tool calls and results  
- Long-term memories from AgentCore Memory
- Filters out OTEL telemetry noise

Works with any agent (supervisor or sub-agents) to show that agent's portion of the conversation.

Usage:
    python show_agent_logs.py supervisor --profile flex-east
    python show_agent_logs.py personalization --minutes 60 --profile flex-east
"""

import json
import sys
import os
import argparse
from datetime import datetime, timedelta
import boto3
from typing import List, Dict, Any
from pathlib import Path

# Global configuration
CDK_PROJECT_DIR = "guidance-for-multi-agent-orchestration-bedrock-agentcore"


def get_log_group_from_cdk(agent_name: str, region: str, profile: str = None) -> str:
    """Get log group name from CDK outputs."""
    session = boto3.Session(profile_name=profile, region_name=region)
    cfn_client = session.client('cloudformation')
    
    # Map agent names to stack names and output keys
    stack_map = {
        'supervisor': ('CustomerSupportAssistantStack', 'SupervisorAgentRuntimeArn'),
        'personalization': ('PersonalizationAgentStack', 'PersonalizationAgentRuntimeArn'),
        'order-management': ('OrderManagementAgentStack', 'OrderManagementAgentRuntimeArn'),
        'product-recommendation': ('ProductRecommendationAgentStack', 'ProductRecommendationAgentRuntimeArn'),
        'troubleshooting': ('TroubleshootingAgentStack', 'TroubleshootingAgentRuntimeArn')
    }
    
    stack_info = stack_map.get(agent_name)
    if not stack_info:
        raise ValueError(f"Unknown agent: {agent_name}. Valid options: {', '.join(stack_map.keys())}")
    
    stack_name, output_key = stack_info
    print(f"Looking up runtime ARN for {agent_name} agent from stack {stack_name}...")
    
    try:
        response = cfn_client.describe_stacks(StackName=stack_name)
        outputs = response['Stacks'][0]['Outputs']
        
        # Find runtime ARN output
        runtime_arn = None
        for output in outputs:
            if output['OutputKey'] == output_key:
                runtime_arn = output['OutputValue']
                break
        
        if not runtime_arn:
            raise ValueError(f"No {output_key} output found in stack {stack_name}")
        
        # Extract runtime ID from ARN
        # ARN format: arn:aws:bedrock-agentcore:region:account:runtime/runtime-id/runtime-endpoint/DEFAULT:DEFAULT
        runtime_id = runtime_arn.split('/')[1]
        
        # Construct log group name
        log_group = f"/aws/bedrock-agentcore/runtimes/{runtime_id}-DEFAULT"
        print(f"Found runtime ID: {runtime_id}")
        print(f"Log group: {log_group}\n")
        return log_group
        
    except Exception as e:
        raise ValueError(f"Failed to get CDK outputs: {e}")


def fetch_logs(log_group: str, agent_name: str, minutes: int, region: str, profile: str = None) -> List[Dict]:
    """Fetch logs from CloudWatch and save to file."""
    session = boto3.Session(profile_name=profile, region_name=region)
    logs_client = session.client('logs')
    
    start_time = int((datetime.now() - timedelta(minutes=minutes)).timestamp() * 1000)
    
    print(f"Fetching logs from {log_group}...")
    print(f"Time range: last {minutes} minutes")
    
    response = logs_client.filter_log_events(
        logGroupName=log_group,
        startTime=start_time,
        limit=1000
    )
    
    events = response.get('events', [])
    
    # Save raw logs to file
    log_dir = Path(__file__).parent / 'test_logs'
    log_dir.mkdir(exist_ok=True)
    output_file = log_dir / f"agent_logs_{agent_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(events, f, indent=2)
    
    print(f"Raw logs saved to: {output_file}")
    print(f"Total events: {len(events)}\n")
    
    return events


def extract_memory_facts(events: List[Dict]) -> Dict[str, Any]:
    """Extract and deduplicate memory facts and preferences from <user_context> blocks."""
    facts = set()
    preferences = []
    
    for event in events:
        message = event.get('message', '')
        
        # Find all <user_context> blocks
        if '<user_context>' in message:
            import re
            contexts = re.findall(r'<user_context>(.*?)</user_context>', message, re.DOTALL)
            
            for context in contexts:
                # Split by \n to get individual items
                items = context.split('\\n')
                
                for item in items:
                    item = item.strip()
                    if not item or len(item) < 10:
                        continue
                    
                    # Try to parse as JSON (preferences) - try multiple unescape levels
                    if item.startswith('{'):
                        parsed = False
                        # Try different levels of unescaping
                        for unescape_passes in range(3):
                            try:
                                test_item = item
                                for _ in range(unescape_passes + 1):
                                    test_item = test_item.replace('\\"', '"').replace('\\\\', '\\')
                                
                                obj = json.loads(test_item)
                                if 'preference' in obj and 'context' in obj:
                                    pref_entry = {
                                        'preference': obj['preference'],
                                        'context': obj['context'],
                                        'categories': obj.get('categories', [])
                                    }
                                    if pref_entry not in preferences:
                                        preferences.append(pref_entry)
                                    parsed = True
                                    break
                            except:
                                continue
                        
                        # Skip JSON strings that couldn't be parsed (don't add as facts)
                        if not parsed:
                            continue
                    else:
                        # Plain text fact - clean up and normalize
                        item = item.replace('\\"', '"').rstrip('\\')
                        if item and item not in facts:
                            facts.add(item)
    
    return {
        'facts': sorted(list(facts)),
        'preferences': preferences
    }


def parse_logs(events: List[Dict]) -> Dict[str, Any]:
    """Parse logs and extract timing, tool calls, and reasoning."""
    
    if not events:
        return {"error": "No events found"}
    
    first_ts = events[0]['timestamp']
    last_ts = events[-1]['timestamp']
    duration = (last_ts - first_ts) / 1000
    
    # Track what we've already seen to avoid duplicates
    seen_content = set()
    timeline = []
    
    for event in events:
        ts = (event['timestamp'] - first_ts) / 1000
        message = event.get('message', '')
        
        # Parse JSON messages
        try:
            log_data = json.loads(message)
            body = log_data.get('body', {})
            scope = log_data.get('scope', {}).get('name', '')
            
            # Handle Strands telemetry format
            if 'strands' in scope.lower() and isinstance(body, dict):
                if 'output' in body:
                    output_msgs = body['output'].get('messages', [])
                    for msg in output_msgs:
                        content = msg.get('content', {})
                        
                        # Handle both streaming and synchronous formats
                        message_str = None
                        if isinstance(content, dict):
                            # Streaming format uses 'content' key
                            message_str = content.get('content')
                            # Synchronous format uses 'message' key
                            if not message_str:
                                message_str = content.get('message')
                        
                        if message_str:
                            try:
                                # Parse the message JSON
                                message_data = json.loads(message_str)
                                
                                event_data = {
                                    'time': ts,
                                    'texts': [],
                                    'tool_calls': [],
                                    'tool_results': []
                                }
                                
                                # Extract text and tool use from message
                                if isinstance(message_data, list):
                                    for item in message_data:
                                        item_key = json.dumps(item, sort_keys=True)
                                        if item_key in seen_content:
                                            continue
                                        seen_content.add(item_key)
                                        
                                        if 'text' in item:
                                            event_data['texts'].append(item['text'])
                                        elif 'toolUse' in item:
                                            tool_use = item['toolUse']
                                            event_data['tool_calls'].append({
                                                'name': tool_use['name'],
                                                'input': tool_use['input']
                                            })
                                        elif 'toolResult' in item:
                                            result = item['toolResult']
                                            content_list = result.get('content', [])
                                            result_text = ''
                                            if content_list and isinstance(content_list, list) and len(content_list) > 0:
                                                result_text = content_list[0].get('text', '')[:300]
                                            event_data['tool_results'].append({
                                                'tool_id': result.get('toolUseId', ''),
                                                'preview': result_text
                                            })
                                
                                if event_data['texts'] or event_data['tool_calls'] or event_data['tool_results']:
                                    timeline.append(event_data)
                            except:
                                # If message isn't JSON, treat as plain text
                                if message_str and message_str not in seen_content:
                                    seen_content.add(message_str)
                                    timeline.append({
                                        'time': ts,
                                        'texts': [message_str],
                                        'tool_calls': [],
                                        'tool_results': []
                                    })
            
            # Extract content array (original format)
            elif isinstance(body, dict) and 'content' in body:
                content_items = body.get('content', [])
                
                # Group new items for this event
                event_data = {
                    'time': ts,
                    'texts': [],
                    'tool_calls': [],
                    'tool_results': []
                }
                
                for item in content_items:
                    # Create unique key for deduplication
                    item_key = json.dumps(item, sort_keys=True)
                    
                    if item_key in seen_content:
                        continue  # Skip duplicates
                    
                    seen_content.add(item_key)
                    
                    if 'toolUse' in item:
                        tool_use = item['toolUse']
                        event_data['tool_calls'].append({
                            'name': tool_use['name'],
                            'input': tool_use['input']
                        })
                    
                    elif 'toolResult' in item:
                        result = item['toolResult']
                        content = result.get('content', [])
                        result_text = ''
                        if content and isinstance(content, list) and len(content) > 0:
                            result_text = content[0].get('text', '')[:300]
                        event_data['tool_results'].append({
                            'tool_id': result.get('toolUseId', ''),
                            'preview': result_text
                        })
                    
                    elif 'text' in item:
                        text = item['text']
                        event_data['texts'].append(text)
                
                # Add to timeline if there's any NEW content
                if event_data['texts'] or event_data['tool_calls'] or event_data['tool_results']:
                    timeline.append(event_data)
            
            # Extract INFO logs (agent-specific logging)
            if isinstance(body, str):
                if 'Invocation completed successfully' in body:
                    timeline.append({
                        'time': ts,
                        'type': 'completion',
                        'text': body
                    })
                elif 'Request processed successfully' in body:
                    timeline.append({
                        'time': ts,
                        'type': 'info',
                        'text': body
                    })
                elif 'Structured response' in body:
                    timeline.append({
                        'time': ts,
                        'type': 'info',
                        'text': 'Structured output generated'
                    })
            
        except json.JSONDecodeError:
            pass
    
    # Sort by time
    timeline.sort(key=lambda x: x['time'])
    
    # Extract memory facts
    memory_facts = extract_memory_facts(events)
    
    return {
        'duration': f"{duration:.1f}s",
        'total_events': len(events),
        'timeline': timeline,
        'memory_facts': memory_facts
    }


def print_analysis(analysis: Dict[str, Any], agent_name: str):
    """Print formatted analysis."""
    
    print("=" * 80)
    print(f"AGENT PERFORMANCE ANALYSIS: {agent_name}")
    print("=" * 80)
    print(f"\nDuration: {analysis['duration']}")
    print(f"Total Events: {analysis['total_events']}")
    
    print("\n" + "-" * 80)
    print("COMPLETE TIMELINE")
    print("-" * 80)
    
    for event in analysis['timeline']:
        ts = event['time']
        
        # Handle grouped content events
        if 'texts' in event:
            # Print all text content
            for text in event['texts']:
                if len(text) > 500:
                    print(f"\n[{ts:6.1f}s] 📝 RESPONSE: {text[:300]}...")
                elif len(text) > 50:
                    print(f"[{ts:6.1f}s] 💭 REASONING: {text}")
                else:
                    print(f"[{ts:6.1f}s] 💬 {text}")
            
            # Print tool calls
            for tool in event['tool_calls']:
                print(f"[{ts:6.1f}s] 🔧 TOOL CALL: {tool['name']}")
                print(f"           Input: {json.dumps(tool['input'], indent=19)[1:]}")
            
            # Print tool results
            for result in event['tool_results']:
                print(f"[{ts:6.1f}s] ✅ TOOL RESULT")
                if result.get('preview'):
                    print(f"           {result['preview']}...")
        
        # Handle simple events
        elif event.get('type') == 'completion':
            print(f"\n[{ts:6.1f}s] ✨ {event['text']}")
        
        elif event.get('type') == 'info':
            print(f"[{ts:6.1f}s] ℹ️  {event['text']}")
    
    # Print memory section
    memory_data = analysis.get('memory_facts', {})
    if memory_data:
        facts = memory_data.get('facts', [])
        preferences = memory_data.get('preferences', [])
        
        if facts or preferences:
            print("\n" + "=" * 80)
            print("LONG-TERM MEMORY ACCUMULATED")
            print("=" * 80)
            
            if facts:
                print(f"\n📋 FACTS ({len(facts)} unique):")
                print("-" * 80)
                for i, fact in enumerate(facts, 1):
                    print(f"{i}. {fact}")
            
            if preferences:
                print(f"\n💡 PREFERENCES ({len(preferences)} unique):")
                print("-" * 80)
                for i, pref in enumerate(preferences, 1):
                    print(f"\n{i}. {pref['preference']}")
                    print(f"   Context: {pref['context']}")
                    if pref.get('categories'):
                        print(f"   Categories: {', '.join(pref['categories'])}")
    
    print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description='Analyze AgentCore runtime performance',
        epilog='Valid agent names: supervisor, personalization, order-management, product-recommendation, troubleshooting'
    )
    parser.add_argument('agent_name', help='Agent name (e.g., supervisor, personalization)')
    parser.add_argument('--minutes', type=int, default=30, help='Minutes of logs to fetch (default: 30)')
    parser.add_argument('--region', default='us-east-1', help='AWS region (default: us-east-1)')
    parser.add_argument('--profile', help='AWS profile name')
    
    args = parser.parse_args()
    
    # Get log group from CDK
    log_group = get_log_group_from_cdk(args.agent_name, args.region, args.profile)
    
    # Fetch logs
    events = fetch_logs(log_group, args.agent_name, args.minutes, args.region, args.profile)
    
    if not events:
        print("No logs found in the specified time range")
        sys.exit(1)
    
    # Parse and analyze
    analysis = parse_logs(events)
    
    # Print results
    print_analysis(analysis, args.agent_name)


if __name__ == '__main__':
    main()
