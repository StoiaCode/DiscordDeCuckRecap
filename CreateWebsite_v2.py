#!/usr/bin/env python3
"""
Discord Stats Website Generator
Creates a beautiful stats dashboard from the Discord analysis database
"""

import sqlite3
import json
import argparse
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
import webbrowser
import threading
import os

# ============= CONFIGURATION =============
TARGET_YEAR = 2025  # Change this for future years!
DB_FILE = "discord_analysis.db"
OUTPUT_FILE = "discord_stats.html"
PORT = 8080
# =========================================

def get_stats_data(db_path, user_id):
    """Extract all statistics from the database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    stats = {}
    
    # Get target year from first message
    cursor.execute('SELECT MAX(message_count) FROM channels')
    if cursor.fetchone()[0] is None:
        print("❌ No data found in database!")
        return None
    
    # Total messages and attachments
    cursor.execute('SELECT SUM(message_count), SUM(messages_with_attachments) FROM channels')
    total_messages, total_attachments = cursor.fetchone()
    stats['total_messages'] = total_messages or 0
    stats['total_attachments'] = total_attachments or 0
    
    # Server stats
    cursor.execute('''
        SELECT server_name, SUM(message_count) as total, SUM(messages_with_attachments) as attachments
        FROM channels 
        WHERE channel_type NOT IN ('DM', 'GROUP_DM') AND server_name IS NOT NULL
        GROUP BY server_id
        ORDER BY total DESC
    ''')
    stats['servers'] = [
        {'name': name, 'count': count, 'attachments': att}
        for name, count, att in cursor.fetchall()
    ]
    
    # DM stats (top 20) - filter out user's own ID and lookup usernames
    cursor.execute('''
        SELECT recipients, message_count, messages_with_attachments
        FROM channels
        WHERE channel_type = 'DM'
        ORDER BY message_count DESC
        LIMIT 20
    ''')

    dms_data = []
    for rec, count, att in cursor.fetchall():
        recipients = json.loads(rec)
        # Get the other user's ID (not our own)
        other_user_id = recipients[0] if recipients[0] != user_id else recipients[1] if len(recipients) > 1 else recipients[0]

        # Look up username
        cursor.execute('SELECT username FROM users WHERE user_id = ?', (other_user_id,))
        result = cursor.fetchone()
        username = result[0] if result else None

        dms_data.append({
            'user_id': other_user_id,
            'username': username,
            'count': count,
            'attachments': att
        })

    stats['dms'] = dms_data
    
    # Group DM stats - with username lookup
    cursor.execute('''
        SELECT recipients, message_count, messages_with_attachments
        FROM channels 
        WHERE channel_type = 'GROUP_DM'
        ORDER BY message_count DESC
    ''')
    
    group_dms_data = []
    for rec, count, att in cursor.fetchall():
        recipients = json.loads(rec)
        
        # Look up usernames for all recipients
        usernames = []
        for uid in recipients:
            if uid == user_id:
                continue  # Skip own user ID
            cursor.execute('SELECT username FROM users WHERE user_id = ?', (uid,))
            result = cursor.fetchone()
            if result:
                usernames.append(result[0])
        
        group_dms_data.append({
            'recipient_count': len(recipients),
            'usernames': usernames,
            'count': count,
            'attachments': att
        })
    
    stats['group_dms'] = group_dms_data
    
    # Top emotes
    cursor.execute('''
        SELECT emote_name, usage_count
        FROM emotes
        ORDER BY usage_count DESC
        LIMIT 50
    ''')
    stats['emotes'] = [
        {'name': name, 'count': count}
        for name, count in cursor.fetchall()
    ]
    
    # File types
    cursor.execute('''
        SELECT extension, count
        FROM file_types
        ORDER BY count DESC
    ''')
    stats['file_types'] = [
        {'ext': ext, 'count': count}
        for ext, count in cursor.fetchall()
    ]
    
    # Channel type breakdown
    cursor.execute('''
        SELECT channel_type, COUNT(*) as channels, SUM(message_count) as messages
        FROM channels
        WHERE message_count > 0
        GROUP BY channel_type
    ''')
    stats['channel_breakdown'] = [
        {'type': ctype, 'channels': channels, 'messages': messages}
        for ctype, channels, messages in cursor.fetchall()
    ]
    
    conn.close()
    return stats

def generate_html(stats):
    """Generate the HTML page with stats"""
    
    max_server_count = max([s['count'] for s in stats['servers']], default=1)
    max_dm_count = max([d['count'] for d in stats['dms']], default=1)
    max_group_dm_count = max([g['count'] for g in stats['group_dms']], default=1)
    max_emote_count = max([e['count'] for e in stats['emotes']], default=1)
    max_file_count = max([f['count'] for f in stats['file_types']], default=1)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Discord Stats {TARGET_YEAR}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            padding: 20px;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        header {{
            background: white;
            border-radius: 20px;
            padding: 40px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            text-align: center;
        }}
        
        h1 {{
            font-size: 3em;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }}
        
        .subtitle {{
            color: #666;
            font-size: 1.2em;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .stat-card {{
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }}
        
        .stat-card:hover {{
            transform: translateY(-5px);
        }}
        
        .stat-number {{
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }}
        
        .stat-label {{
            color: #666;
            font-size: 1em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .section {{
            background: white;
            border-radius: 20px;
            padding: 40px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        
        h2 {{
            font-size: 2em;
            margin-bottom: 30px;
            color: #333;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }}
        
        .bar-item {{
            margin-bottom: 20px;
        }}
        
        .bar-header {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 1.1em;
        }}
        
        .bar-name {{
            font-weight: 600;
            color: #333;
        }}
        
        .bar-count {{
            color: #667eea;
            font-weight: bold;
        }}
        
        .bar-container {{
            background: #f0f0f0;
            border-radius: 10px;
            height: 30px;
            overflow: hidden;
            position: relative;
        }}
        
        .bar-fill {{
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            height: 100%;
            border-radius: 10px;
            transition: width 1s ease;
            display: flex;
            align-items: center;
            padding: 0 15px;
            color: white;
            font-weight: bold;
            font-size: 0.9em;
        }}
        
        .bar-fill.animated {{
            animation: fillBar 1.5s ease-out;
        }}
        
        @keyframes fillBar {{
            from {{ width: 0; }}
        }}
        
        .emote-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 15px;
        }}
        
        .emote-item {{
            background: #f9f9f9;
            padding: 15px;
            border-radius: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: background 0.3s ease;
        }}
        
        .emote-item:hover {{
            background: #e9e9e9;
        }}
        
        .emote-name {{
            font-family: monospace;
            font-size: 1.1em;
            color: #333;
        }}
        
        .emote-count {{
            background: #667eea;
            color: white;
            padding: 5px 12px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 0.9em;
        }}
        
        .file-type-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 15px;
        }}
        
        .file-type-item {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 3px 10px rgba(0,0,0,0.2);
        }}
        
        .file-ext {{
            font-size: 1.5em;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .file-count {{
            font-size: 1.2em;
            opacity: 0.9;
        }}
        
        .dm-list {{
            display: grid;
            gap: 15px;
        }}
        
        .dm-item {{
            background: #f9f9f9;
            padding: 20px;
            border-radius: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .dm-id {{
            font-family: monospace;
            color: #999;
            font-size: 0.85em;
            margin-top: 5px;
        }}
        
        .dm-stats {{
            display: flex;
            gap: 20px;
            align-items: center;
        }}
        
        .dm-count {{
            font-size: 1.5em;
            font-weight: bold;
            color: #667eea;
        }}
        
        .dm-attachments {{
            color: #999;
            font-size: 0.9em;
        }}
        
        footer {{
            text-align: center;
            color: white;
            margin-top: 50px;
            padding: 20px;
            font-size: 0.9em;
        }}
        
        .percentage {{
            font-size: 0.8em;
            opacity: 0.8;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 Discord Stats {TARGET_YEAR}</h1>
            <p class="subtitle">Your Year in Review</p>
        </header>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{stats['total_messages']:,}</div>
                <div class="stat-label">Total Messages</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{len(stats['servers'])}</div>
                <div class="stat-label">Servers</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{len(stats['dms']) + len(stats['group_dms'])}</div>
                <div class="stat-label">Direct Chats</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['total_attachments']:,}</div>
                <div class="stat-label">Attachments</div>
            </div>
        </div>
        
        <div class="section">
            <h2>🏆 Top Servers</h2>
            <div class="bar-list">
"""
    
    for server in stats['servers'][:15]:
        percentage = (server['count'] / max_server_count * 100)
        attach_rate = (server['attachments'] / server['count'] * 100) if server['count'] > 0 else 0
        html += f"""
                <div class="bar-item">
                    <div class="bar-header">
                        <span class="bar-name">{server['name']}</span>
                        <span class="bar-count">{server['count']:,} messages <span class="percentage">({attach_rate:.1f}% with attachments)</span></span>
                    </div>
                    <div class="bar-container">
                        <div class="bar-fill animated" style="width: {percentage}%"></div>
                    </div>
                </div>
"""
    
    html += """
            </div>
        </div>
        
        <div class="section">
            <h2>💬 Top Direct Messages</h2>
            <div class="dm-list">
"""
    
    for dm in stats['dms'][:15]:
        attach_rate = (dm['attachments'] / dm['count'] * 100) if dm['count'] > 0 else 0
        
        # Display username if available, otherwise show user ID
        if dm.get('username'):
            display_name = dm['username']
            subtitle = f"User ID: {dm['user_id']}"
        else:
            display_name = f"User ID: {dm['user_id']}"
            subtitle = ""
        
        html += f"""
                <div class="dm-item">
                    <div>
                        <div class="bar-name">{display_name}</div>
                        {'<div class="dm-id">' + subtitle + '</div>' if subtitle else ''}
                    </div>
                    <div class="dm-stats">
                        <div class="dm-count">{dm['count']:,}</div>
                        <div class="dm-attachments">📎 {dm['attachments']:,} ({attach_rate:.1f}%)</div>
                    </div>
                </div>
"""
    
    html += """
            </div>
        </div>
"""
    
    if stats['group_dms']:
        html += """
        <div class="section">
            <h2>👥 Group Chats</h2>
            <div class="bar-list">
"""
        for idx, gdm in enumerate(stats['group_dms'][:10], 1):
            # Use group DM max for percentage calculation
            percentage = (gdm['count'] / max_group_dm_count * 100) if max_group_dm_count > 0 else 0
            
            # Build display name
            if gdm.get('usernames') and len(gdm['usernames']) > 0:
                if len(gdm['usernames']) <= 3:
                    display_name = f"Group with {', '.join(gdm['usernames'])}"
                else:
                    display_name = f"Group with {', '.join(gdm['usernames'][:3])} and {len(gdm['usernames']) - 3} others"
            else:
                display_name = f"Group Chat #{idx}"
            
            html += f"""
                <div class="bar-item">
                    <div class="bar-header">
                        <span class="bar-name">{display_name} ({gdm['recipient_count']} members)</span>
                        <span class="bar-count">{gdm['count']:,} messages</span>
                    </div>
                    <div class="bar-container">
                        <div class="bar-fill animated" style="width: {percentage}%"></div>
                    </div>
                </div>
"""
        html += """
            </div>
        </div>
"""
    
    html += """
        <div class="section">
            <h2>😀 Most Used Emotes</h2>
            <div class="emote-grid">
"""
    
    for emote in stats['emotes'][:30]:
        html += f"""
                <div class="emote-item">
                    <span class="emote-name">:{emote['name']}:</span>
                    <span class="emote-count">{emote['count']:,}</span>
                </div>
"""
    
    html += """
            </div>
        </div>
        
        <div class="section">
            <h2>📎 Attachment Types</h2>
            <div class="file-type-grid">
"""
    
    for ftype in stats['file_types'][:20]:
        html += f"""
                <div class="file-type-item">
                    <div class="file-ext">.{ftype['ext']}</div>
                    <div class="file-count">{ftype['count']:,} files</div>
                </div>
"""
    
    html += f"""
            </div>
        </div>
        
        <footer>
            <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Discord GDPR Data Analysis</p>
        </footer>
    </div>
</body>
</html>
"""
    
    return html

def save_html(html, filename):
    """Save HTML to file"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ Stats page saved to: {filename}")

def serve_html(filename, port):
    """Start a simple HTTP server to serve the HTML file"""
    
    class CustomHandler(SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Suppress logs
    
    os.chdir(os.path.dirname(os.path.abspath(filename)) or '.')
    
    server = HTTPServer(('localhost', port), CustomHandler)
    print(f"🌐 Server starting at http://localhost:{port}/{os.path.basename(filename)}")
    print(f"📊 Opening browser...")
    
    # Open browser after a short delay
    def open_browser():
        import time
        time.sleep(1)
        webbrowser.open(f'http://localhost:{port}/{os.path.basename(filename)}')
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    print(f"\n✨ Server running! Press Ctrl+C to stop.\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n✅ Server stopped.")
        server.shutdown()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate Discord stats website')
    parser.add_argument('--user-id', type=str, required=True,
                       help='Your Discord User ID (required)')
    parser.add_argument('-o', '--output', default=OUTPUT_FILE,
                       help=f'Output HTML file (default: {OUTPUT_FILE})')
    parser.add_argument('-s', '--serve', action='store_true',
                       help='Start web server after generating')
    parser.add_argument('-p', '--port', type=int, default=PORT,
                       help=f'Port for web server (default: {PORT})')
    parser.add_argument('--db', default=DB_FILE,
                       help=f'Database file (default: {DB_FILE})')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.db):
        print(f"❌ Database not found: {args.db}")
        print("   Run the analyzer script first to create the database.")
        exit(1)
    
    print("📊 Generating Discord stats website...")
    
    stats = get_stats_data(args.db, args.user_id)
    if not stats:
        exit(1)
    
    html = generate_html(stats)
    save_html(html, args.output)
    
    if args.serve:
        serve_html(args.output, args.port)
    else:
        print(f"\n💡 To view with live server, run:")
        print(f"   python {os.path.basename(__file__)} --user-id {args.user_id} --serve")