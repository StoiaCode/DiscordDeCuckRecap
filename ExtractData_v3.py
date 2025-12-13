#!/usr/bin/env python3
"""
Discord GDPR Data Analyzer v3
Now with emote tracking and attachment analysis!
"""

import json
import os
import sqlite3
import re
from datetime import datetime
from pathlib import Path
import time
import argparse
from collections import defaultdict

# ============= CONFIGURATION =============
USER_ID = "YOUR_USER_ID_HERE"  # Replace with your Discord user ID
TARGET_YEAR = 2025  # Change this for future years!
MESSAGES_DIR = "./Messages"
DB_FILE = "discord_analysis.db"
# =========================================

class DiscordAnalyzer:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.conn = sqlite3.connect(DB_FILE)
        self.setup_database()
        self.processed_count = 0
        self.skipped_count = 0
        self.error_count = 0
        
        # Regex patterns
        self.emote_pattern = re.compile(r'<a?:([^:]+):(\d+)>')  # Matches <:name:id> or <a:name:id>
        self.file_extension_pattern = re.compile(r'\.([a-zA-Z0-9]+)(?:\?|$)')
        
    def setup_database(self):
        """Create database tables"""
        cursor = self.conn.cursor()
        
        # Table for channels
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                folder_name TEXT PRIMARY KEY,
                channel_id TEXT,
                channel_type TEXT,
                channel_name TEXT,
                server_id TEXT,
                server_name TEXT,
                recipients TEXT,
                message_count INTEGER,
                messages_with_attachments INTEGER,
                processed INTEGER DEFAULT 0
            )
        ''')
        
        # Table for emote usage
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS emotes (
                emote_id TEXT PRIMARY KEY,
                emote_name TEXT,
                usage_count INTEGER DEFAULT 0
            )
        ''')
        
        # Table for attachment file types
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_types (
                extension TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0
            )
        ''')
        
        # Table for detailed messages (optional)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                folder_name TEXT,
                timestamp TEXT,
                year INTEGER,
                month INTEGER,
                day INTEGER,
                has_content INTEGER,
                has_attachments INTEGER,
                FOREIGN KEY (folder_name) REFERENCES channels(folder_name)
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_year ON messages(year)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_folder ON messages(folder_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_processed ON channels(processed)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_emote_count ON emotes(usage_count)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_count ON file_types(count)')
        
        self.conn.commit()
    
    def is_target_year(self, timestamp_str):
        """Check if a message timestamp is in the target year"""
        try:
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            return dt.year == TARGET_YEAR
        except:
            return False
    
    def parse_timestamp(self, timestamp_str):
        """Parse timestamp into components"""
        try:
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            return dt.year, dt.month, dt.day
        except:
            return None, None, None
    
    def extract_emotes(self, content):
        """Extract all emotes from message content"""
        if not content:
            return []
        
        matches = self.emote_pattern.findall(content)
        # Returns list of tuples: [(name, id), (name, id), ...]
        return [(name, emote_id) for name, emote_id in matches]
    
    def extract_file_types(self, attachments):
        """Extract file extensions from attachment URLs"""
        if not attachments:
            return []
        
        # Split by newlines or commas in case there are multiple attachments
        urls = attachments.replace(',', '\n').split('\n')
        extensions = []
        
        for url in urls:
            url = url.strip()
            if not url:
                continue
            
            match = self.file_extension_pattern.search(url)
            if match:
                ext = match.group(1).lower()
                extensions.append(ext)
        
        return extensions
    
    def update_emote_count(self, emote_name, emote_id, count=1):
        """Update emote usage count in database"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO emotes (emote_id, emote_name, usage_count)
            VALUES (?, ?, ?)
            ON CONFLICT(emote_id) DO UPDATE SET
                usage_count = usage_count + ?,
                emote_name = ?
        ''', (emote_id, emote_name, count, count, emote_name))
    
    def update_file_type_count(self, extension, count=1):
        """Update file type count in database"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO file_types (extension, count)
            VALUES (?, ?)
            ON CONFLICT(extension) DO UPDATE SET
                count = count + ?
        ''', (extension, count, count))
    
    def process_folder(self, folder_path, store_messages=False):
        """Process a single channel folder"""
        folder_name = os.path.basename(folder_path)
        
        # Check if already processed
        cursor = self.conn.cursor()
        cursor.execute('SELECT processed FROM channels WHERE folder_name = ?', (folder_name,))
        result = cursor.fetchone()
        if result and result[0] == 1:
            if self.verbose:
                print(f"⏭️  Skipping {folder_name} (already processed)")
            return
        
        channel_file = os.path.join(folder_path, "channel.json")
        messages_file = os.path.join(folder_path, "messages.json")
        
        # Check if both files exist
        if not os.path.exists(channel_file) or not os.path.exists(messages_file):
            self.error_count += 1
            if self.verbose:
                print(f"❌ {folder_name}: Missing files")
            return
        
        try:
            # Load channel info
            with open(channel_file, 'r', encoding='utf-8') as f:
                channel_data = json.load(f)
            
            # Load messages
            with open(messages_file, 'r', encoding='utf-8') as f:
                messages = json.load(f)
            
            if not messages:
                self.skipped_count += 1
                if self.verbose:
                    print(f"⏭️  {folder_name}: No messages")
                self._mark_processed(folder_name, channel_data, 0, 0)
                return
            
            # Check if the FIRST (newest) message is in target year or later
            first_message = messages[0]
            first_timestamp = first_message.get("Timestamp", "")
            
            try:
                first_dt = datetime.strptime(first_timestamp, "%Y-%m-%d %H:%M:%S")
                if first_dt.year < TARGET_YEAR:
                    # Newest message is before target year
                    self.skipped_count += 1
                    if self.verbose:
                        print(f"⏭️  {folder_name}: No {TARGET_YEAR} messages (newest: {first_timestamp})")
                    self._mark_processed(folder_name, channel_data, 0, 0)
                    return
            except:
                self.error_count += 1
                if self.verbose:
                    print(f"❌ {folder_name}: Invalid timestamp format")
                return
            
            # Count messages from target year and analyze content
            count_target_year = 0
            messages_with_attachments = 0
            emote_counts = defaultdict(int)  # {emote_id: count}
            emote_names = {}  # {emote_id: name}
            file_type_counts = defaultdict(int)  # {extension: count}
            
            for message in messages:
                timestamp = message.get("Timestamp", "")
                if self.is_target_year(timestamp):
                    count_target_year += 1
                    
                    # Extract and count emotes
                    content = message.get("Contents", "")
                    emotes = self.extract_emotes(content)
                    for emote_name, emote_id in emotes:
                        emote_counts[emote_id] += 1
                        emote_names[emote_id] = emote_name
                    
                    # Extract and count file types
                    attachments = message.get("Attachments", "")
                    file_types = self.extract_file_types(attachments)
                    if file_types:
                        messages_with_attachments += 1
                        for ext in file_types:
                            file_type_counts[ext] += 1
                    
                    # Store individual message if requested
                    if store_messages:
                        year, month, day = self.parse_timestamp(timestamp)
                        cursor.execute('''
                            INSERT OR IGNORE INTO messages 
                            (message_id, folder_name, timestamp, year, month, day, 
                             has_content, has_attachments)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            str(message.get("ID", "")),
                            folder_name,
                            timestamp,
                            year, month, day,
                            1 if content else 0,
                            1 if attachments else 0
                        ))
                else:
                    # Messages are newest first, so we can stop here
                    break
            
            if count_target_year == 0:
                self.skipped_count += 1
                if self.verbose:
                    print(f"⏭️  {folder_name}: No {TARGET_YEAR} messages after scan")
                self._mark_processed(folder_name, channel_data, 0, 0)
                return
            
            # Update emote counts in database
            for emote_id, count in emote_counts.items():
                self.update_emote_count(emote_names[emote_id], emote_id, count)
            
            # Update file type counts in database
            for ext, count in file_type_counts.items():
                self.update_file_type_count(ext, count)
            
            # Store channel info
            self._mark_processed(folder_name, channel_data, count_target_year, messages_with_attachments)
            self.processed_count += 1
            
            if self.verbose:
                channel_type = channel_data.get("type")
                if channel_type in ["DM", "GROUP_DM"]:
                    recipient_count = len(channel_data.get("recipients", []))
                    dm_type = "Group DM" if recipient_count > 2 else "DM"
                    print(f"✅ {folder_name}: {count_target_year} msgs, {len(emote_counts)} emotes, {messages_with_attachments} w/attachments ({dm_type})")
                else:
                    server_name = channel_data.get("guild", {}).get("name", "Unknown")
                    channel_name = channel_data.get("name", "unknown")
                    print(f"✅ {folder_name}: {count_target_year} msgs, {len(emote_counts)} emotes, {messages_with_attachments} w/attachments ({server_name} / #{channel_name})")
            
            self.conn.commit()
            
        except Exception as e:
            self.error_count += 1
            if self.verbose:
                print(f"❌ {folder_name}: {str(e)}")
            import traceback
            if self.verbose:
                traceback.print_exc()
    
    def _mark_processed(self, folder_name, channel_data, count, attachments_count):
        """Mark a folder as processed in the database"""
        cursor = self.conn.cursor()
        
        channel_type = channel_data.get("type", "UNKNOWN")
        channel_id = channel_data.get("id", "")
        channel_name = channel_data.get("name", "")
        
        server_id = None
        server_name = None
        recipients = None
        
        if channel_type in ["DM", "GROUP_DM"]:
            recipients = json.dumps(sorted(channel_data.get("recipients", [])))
        else:
            guild = channel_data.get("guild", {})
            server_id = guild.get("id")
            server_name = guild.get("name")
        
        cursor.execute('''
            INSERT OR REPLACE INTO channels 
            (folder_name, channel_id, channel_type, channel_name, 
             server_id, server_name, recipients, message_count, 
             messages_with_attachments, processed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (folder_name, channel_id, channel_type, channel_name,
              server_id, server_name, recipients, count, attachments_count))
    
    def run(self, store_messages=False):
        """Main analysis loop"""
        print("🔍 Discord GDPR Data Analyzer v3")
        print("=" * 60)
        print(f"📅 Analyzing messages from: {TARGET_YEAR}")
        print()
        
        if not os.path.exists(MESSAGES_DIR):
            print(f"❌ Error: {MESSAGES_DIR} directory not found!")
            return
        
        all_folders = [f for f in os.listdir(MESSAGES_DIR) 
                      if os.path.isdir(os.path.join(MESSAGES_DIR, f)) and f.startswith('c')]
        
        total_folders = len(all_folders)
        
        # Check how many already processed
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM channels WHERE processed = 1')
        already_processed = cursor.fetchone()[0]
        
        print(f"📊 Found {total_folders} channel folders")
        print(f"✓  Already processed: {already_processed}")
        print(f"⏳ Remaining: {total_folders - already_processed}")
        if store_messages:
            print(f"💾 Storing individual messages to database")
        print()
        
        start_time = time.time()
        processed_this_run = 0
        
        for idx, folder_name in enumerate(all_folders):
            folder_path = os.path.join(MESSAGES_DIR, folder_name)
            self.process_folder(folder_path, store_messages)
            processed_this_run += 1
            
            # Progress reporting
            if not self.verbose and processed_this_run % 50 == 0:
                elapsed = time.time() - start_time
                rate = processed_this_run / elapsed if elapsed > 0 else 0
                remaining = total_folders - already_processed - processed_this_run
                eta = remaining / rate if rate > 0 else 0
                
                cursor.execute('SELECT SUM(message_count) FROM channels')
                total_messages = cursor.fetchone()[0] or 0
                
                print(f"⚙️  Progress: {already_processed + processed_this_run}/{total_folders} "
                      f"({((already_processed + processed_this_run)/total_folders*100):.1f}%) | "
                      f"Rate: {rate:.1f}/s | "
                      f"ETA: {eta/60:.1f}m | "
                      f"Messages: {total_messages:,}")
            
            # Commit every 100 folders
            if processed_this_run % 100 == 0:
                self.conn.commit()
        
        self.conn.commit()
        self.print_results()
    
    def print_results(self):
        """Print analysis results"""
        cursor = self.conn.cursor()
        
        # Total messages
        cursor.execute('SELECT SUM(message_count) FROM channels')
        total_messages = cursor.fetchone()[0] or 0
        
        # Total attachments
        cursor.execute('SELECT SUM(messages_with_attachments) FROM channels')
        total_with_attachments = cursor.fetchone()[0] or 0
        
        # Server stats
        cursor.execute('''
            SELECT server_id, server_name, SUM(message_count) as total
            FROM channels 
            WHERE channel_type NOT IN ('DM', 'GROUP_DM') 
            GROUP BY server_id
            ORDER BY total DESC
        ''')
        servers = cursor.fetchall()
        
        # DM stats
        cursor.execute('''
            SELECT recipients, SUM(message_count) as total
            FROM channels 
            WHERE channel_type = 'DM'
            GROUP BY recipients
        ''')
        dms = cursor.fetchall()
        
        # Group DM stats
        cursor.execute('''
            SELECT recipients, SUM(message_count) as total
            FROM channels 
            WHERE channel_type = 'GROUP_DM'
            GROUP BY recipients
        ''')
        group_dms = cursor.fetchall()
        
        # Top emotes
        cursor.execute('''
            SELECT emote_name, emote_id, usage_count
            FROM emotes
            ORDER BY usage_count DESC
            LIMIT 20
        ''')
        top_emotes = cursor.fetchall()
        
        # File type stats
        cursor.execute('''
            SELECT extension, count
            FROM file_types
            ORDER BY count DESC
        ''')
        file_types = cursor.fetchall()
        
        print("\n" + "=" * 60)
        print(f"✅ Analysis Complete for {TARGET_YEAR}!")
        print("=" * 60)
        print(f"\n📈 SUMMARY:")
        print(f"   Total Messages: {total_messages:,}")
        print(f"   Messages with Attachments: {total_with_attachments:,} ({total_with_attachments/total_messages*100:.1f}%)" if total_messages > 0 else "   Messages with Attachments: 0")
        print(f"   Unique Emotes Used: {len(top_emotes)}")
        print(f"   Servers: {len(servers)}")
        print(f"   DMs: {len(dms)}")
        print(f"   Group DMs: {len(group_dms)}")
        print(f"   Folders with {TARGET_YEAR} messages: {self.processed_count}")
        print(f"   Folders skipped (no {TARGET_YEAR} messages): {self.skipped_count}")
        print(f"   Folders with errors: {self.error_count}")
        
        print(f"\n🏆 TOP 10 SERVERS:")
        for idx, (server_id, server_name, count) in enumerate(servers[:10], 1):
            print(f"   {idx}. {server_name}: {count:,} messages")
        
        print(f"\n😀 TOP 20 EMOTES:")
        for idx, (name, emote_id, count) in enumerate(top_emotes, 1):
            print(f"   {idx}. :{name}: - {count:,} uses")
        
        print(f"\n📎 ATTACHMENT FILE TYPES:")
        for ext, count in file_types:
            print(f"   .{ext}: {count:,} files")
        
        print(f"\n💾 Database saved to: {DB_FILE}")
        print(f"\n💡 TIP: Use 'python discord_analyzer.py --query' to run custom SQL queries!")


def query_mode(db_file):
    """Interactive query mode"""
    if not os.path.exists(db_file):
        print(f"❌ Database not found: {db_file}")
        print("   Run the analyzer first to create the database.")
        return
    
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    print("🔍 Query Mode - Discord Analysis Database")
    print("=" * 60)
    print("\nUseful queries:")
    print("  1. Top 50 emotes:")
    print("     SELECT emote_name, usage_count FROM emotes")
    print("     ORDER BY usage_count DESC LIMIT 50")
    print()
    print("  2. Find specific emote:")
    print("     SELECT * FROM emotes WHERE emote_name LIKE '%pepe%'")
    print()
    print("  3. File type breakdown:")
    print("     SELECT extension, count FROM file_types")
    print("     ORDER BY count DESC")
    print()
    print("  4. Server channel breakdown:")
    print("     SELECT channel_name, message_count")
    print("     FROM channels WHERE server_name = 'YourServer'")
    print()
    print("Type 'exit' to quit\n")
    
    while True:
        try:
            query = input("SQL> ").strip()
            if query.lower() in ['exit', 'quit']:
                break
            if not query:
                continue
            
            cursor.execute(query)
            results = cursor.fetchall()
            
            if results:
                for row in results:
                    print(row)
                print(f"\n({len(results)} rows)")
            else:
                print("(No results)")
            print()
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}\n")
    
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f'Analyze Discord GDPR data for {TARGET_YEAR}')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Show detailed progress for each folder')
    parser.add_argument('-m', '--store-messages', action='store_true',
                       help='Store individual messages in database (slower, more data)')
    parser.add_argument('-q', '--query', action='store_true',
                       help='Enter query mode to analyze existing database')
    parser.add_argument('--server', type=str,
                       help='Show stats for a specific server (partial name match)')
    parser.add_argument('--emote', type=str,
                       help='Search for a specific emote by name')
    
    args = parser.parse_args()
    
    if args.query:
        query_mode(DB_FILE)
    elif args.server:
        # Quick server lookup
        if not os.path.exists(DB_FILE):
            print(f"❌ Database not found. Run analyzer first.")
        else:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT channel_name, message_count, messages_with_attachments
                FROM channels 
                WHERE server_name LIKE ?
                ORDER BY message_count DESC
            ''', (f'%{args.server}%',))
            results = cursor.fetchall()
            
            if results:
                print(f"\n📊 Channels in servers matching '{args.server}':")
                total = 0
                total_attach = 0
                for channel, count, attach in results:
                    print(f"   #{channel}: {count:,} messages ({attach:,} with attachments)")
                    total += count
                    total_attach += attach
                print(f"\n   TOTAL: {total:,} messages ({total_attach:,} with attachments)")
            else:
                print(f"No servers found matching '{args.server}'")
            conn.close()
    elif args.emote:
        # Quick emote lookup
        if not os.path.exists(DB_FILE):
            print(f"❌ Database not found. Run analyzer first.")
        else:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT emote_name, usage_count
                FROM emotes 
                WHERE emote_name LIKE ?
                ORDER BY usage_count DESC
            ''', (f'%{args.emote}%',))
            results = cursor.fetchall()
            
            if results:
                print(f"\n😀 Emotes matching '{args.emote}':")
                for name, count in results:
                    print(f"   :{name}: - {count:,} uses")
            else:
                print(f"No emotes found matching '{args.emote}'")
            conn.close()
    else:
        analyzer = DiscordAnalyzer(verbose=args.verbose)
        try:
            analyzer.run(store_messages=args.store_messages)
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user.")
            print("✅ Database changes saved. Run again to resume.")
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            analyzer.conn.close()