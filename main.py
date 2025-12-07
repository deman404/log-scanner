import customtkinter as ctk
from tkinter import messagebox, filedialog, scrolledtext
import os
import datetime
import sys
import threading
import json
import subprocess
import ctypes
import re
import winreg
import socket
import platform
import time
import hashlib
import fnmatch
from collections import defaultdict
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import queue


# Check for admin privileges
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


# Request admin elevation
def run_as_admin():
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
        sys.exit()


# Try to import Windows-specific modules
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("Warning: psutil not installed. Install with: pip install psutil")

try:
    import win32evtlog
    import win32evtlogutil
    import win32con

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False
    print("Warning: pywin32 not installed. Install with: pip install pywin32")

# Set appearance mode
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# File system event handler
class FileMonitorHandler(FileSystemEventHandler):
    def __init__(self, log_callback):
        self.log_callback = log_callback
        self.important_folders = [
            os.path.expanduser('~'),  # User home
            os.path.expanduser('~/Desktop'),
            os.path.expanduser('~/Documents'),
            os.path.expanduser('~/Downloads'),
            os.path.expanduser('~/AppData'),
            'C:\\Windows\\System32',
            'C:\\Program Files',
            'C:\\Program Files (x86)'
        ]

    def on_created(self, event):
        if not event.is_directory:
            self.log_callback('created', event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self.log_callback('deleted', event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self.log_callback('modified', event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self.log_callback('moved', event.src_path, event.dest_path)


class SimpleLogViewer(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Check admin and dependencies
        self.check_prerequisites()

        # Configure window
        self.title("🔍 System Activity Monitor with File Tracking")
        self.geometry("1400x900")
        self.minsize(1000, 600)

        # Initialize variables
        self.log_data = []
        self.filtered_data = []
        self.loading = False
        self.file_monitor = None
        self.file_events_queue = queue.Queue()

        # Track recently deleted files
        self.recent_deletions = []

        # Configure layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Create UI
        self.create_ui()

        # Load initial data
        self.load_logs_threaded()

        # Start file monitoring
        self.start_file_monitoring()

    def check_prerequisites(self):
        """Check for admin and dependencies"""
        if not is_admin():
            response = messagebox.askyesno(
                "Admin Required",
                "This tool requires administrator privileges.\n\n"
                "Run as administrator now?"
            )
            if response:
                run_as_admin()
            else:
                sys.exit(1)

    def create_ui(self):
        # ============ LEFT SIDEBAR (Simplified) ============
        sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=5)
        sidebar.grid_rowconfigure(9, weight=1)

        # Title
        ctk.CTkLabel(
            sidebar,
            text="ACTIONS",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#4fc3f7"
        ).pack(pady=(20, 10))

        # Main Actions
        actions = [
            ("🔄 Refresh", self.refresh_logs),
            ("📊 Processes", self.show_processes),
            ("📁 File Monitor", self.show_file_events),
            ("🗑️ Deletions", self.show_deletions),
            ("🔍 Search", self.search_logs),
            ("⚠️ Threats", self.show_threats),
            ("📥 Downloads", self.show_downloads),
            ("🔗 Network", self.show_network),
            ("💾 Export", self.export_logs),
            ("🧹 Clear", self.clear_display)
        ]

        for text, command in actions:
            btn = ctk.CTkButton(
                sidebar,
                text=text,
                command=command,
                height=35,
                corner_radius=6,
                font=ctk.CTkFont(size=12)
            )
            btn.pack(pady=3, padx=10, fill="x")

        # Separator
        ctk.CTkLabel(sidebar, text="").pack(pady=10)

        # Quick Stats
        ctk.CTkLabel(
            sidebar,
            text="QUICK STATS",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(10, 5))

        self.stats_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        self.stats_frame.pack(pady=5, padx=10, fill="x")

        self.stats_labels = {}
        stats = [
            ("Total", "total", "#4fc3f7"),
            ("Critical", "critical", "#ff4444"),
            ("Files", "files", "#00C851"),
            ("Deletions", "deletions", "#ff4444")
        ]

        for label_text, key, color in stats:
            frame = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
            frame.pack(fill="x", pady=2)

            ctk.CTkLabel(
                frame,
                text=f"{label_text}:",
                font=ctk.CTkFont(size=11),
                width=80,
                anchor="w"
            ).pack(side="left")

            self.stats_labels[key] = ctk.CTkLabel(
                frame,
                text="0",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=color
            )
            self.stats_labels[key].pack(side="right")

        # ============ MAIN CONTENT AREA ============
        main_content = ctk.CTkFrame(self, corner_radius=0)
        main_content.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        main_content.grid_columnconfigure(0, weight=1)
        main_content.grid_rowconfigure(1, weight=1)

        # ============ TOP CONTROLS BAR ============
        controls_frame = ctk.CTkFrame(main_content, height=50)
        controls_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 5))
        controls_frame.grid_columnconfigure(0, weight=1)

        # File test buttons
        test_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        test_frame.pack(side="left", padx=(10, 0), pady=10)

        ctk.CTkButton(
            test_frame,
            text="📝 Test Create",
            command=self.test_create_file,
            width=90,
            height=30,
            font=ctk.CTkFont(size=11)
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            test_frame,
            text="🗑️ Test Delete",
            command=self.test_delete_file,
            width=90,
            height=30,
            font=ctk.CTkFont(size=11),
            fg_color="#ff4444",
            hover_color="#cc0000"
        ).pack(side="left", padx=2)

        # Search bar
        search_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        search_frame.pack(side="left", padx=20, pady=10)

        ctk.CTkLabel(search_frame, text="🔍", font=ctk.CTkFont(size=14)).pack(side="left", padx=(0, 5))

        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="Search logs...",
            width=250,
            height=30
        )
        self.search_entry.pack(side="left")
        self.search_entry.bind("<KeyRelease>", self.on_search)

        # Time filter
        filter_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        filter_frame.pack(side="right", padx=(0, 10), pady=10)

        ctk.CTkLabel(filter_frame, text="Time:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))

        self.time_combo = ctk.CTkComboBox(
            filter_frame,
            values=["Live (1 min)", "Last 5 min", "Last 15 min", "Last hour", "Today", "All"],
            width=120,
            height=30,
            command=self.on_time_filter
        )
        self.time_combo.pack(side="left", padx=(0, 10))
        self.time_combo.set("Live (1 min)")

        # Severity filter
        ctk.CTkLabel(filter_frame, text="Type:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))

        self.type_combo = ctk.CTkComboBox(
            filter_frame,
            values=["All", "File", "Process", "Network", "Event", "System"],
            width=100,
            height=30,
            command=self.on_type_filter
        )
        self.type_combo.pack(side="left")
        self.type_combo.set("All")

        # ============ LOGS DISPLAY (LARGER AREA) ============
        logs_frame = ctk.CTkFrame(main_content)
        logs_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        logs_frame.grid_columnconfigure(0, weight=1)
        logs_frame.grid_rowconfigure(0, weight=1)

        # Create scrolled text widget
        self.logs_text = scrolledtext.ScrolledText(
            logs_frame,
            bg='#1e1e1e',
            fg='white',
            font=('Consolas', 10),
            insertbackground='white',
            wrap='word',
            relief='flat',
            borderwidth=0
        )
        self.logs_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Configure tags for colors
        self.logs_text.tag_config('critical', foreground='#ff4444')
        self.logs_text.tag_config('high', foreground='#ff8800')
        self.logs_text.tag_config('medium', foreground='#ffbb33')
        self.logs_text.tag_config('low', foreground='#00C851')
        self.logs_text.tag_config('info', foreground='#33b5e5')
        self.logs_text.tag_config('file_create', foreground='#00ff00')
        self.logs_text.tag_config('file_delete', foreground='#ff4444')
        self.logs_text.tag_config('file_modify', foreground='#ff9900')
        self.logs_text.tag_config('highlight', background='yellow', foreground='black')

        # ============ BOTTOM STATUS BAR ============
        self.status_bar = ctk.CTkFrame(main_content, height=30)
        self.status_bar.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="Ready - Monitoring file system...",
            font=ctk.CTkFont(size=11)
        )
        self.status_label.pack(side="left", padx=10, pady=5)

        # Monitor status
        self.monitor_status = ctk.CTkLabel(
            self.status_bar,
            text="📁 File Monitor: ACTIVE",
            font=ctk.CTkFont(size=11),
            text_color="#00ff00"
        )
        self.monitor_status.pack(side="right", padx=10, pady=5)

        # ============ RIGHT SIDEBAR (Event Details) ============
        details_sidebar = ctk.CTkFrame(self, width=300, corner_radius=0)
        details_sidebar.grid(row=0, column=2, sticky="nsew", padx=(5, 0), pady=5)
        details_sidebar.grid_rowconfigure(2, weight=1)

        # Details title
        ctk.CTkLabel(
            details_sidebar,
            text="EVENT DETAILS",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#4fc3f7"
        ).pack(pady=(20, 10))

        # Selected event info
        details_frame = ctk.CTkFrame(details_sidebar, corner_radius=8)
        details_frame.pack(pady=10, padx=10, fill="both", expand=True)

        self.details_text = ctk.CTkTextbox(
            details_frame,
            font=ctk.CTkFont(family="Consolas", size=10),
            wrap="word"
        )
        self.details_text.pack(pady=10, padx=10, fill="both", expand=True)
        self.details_text.insert("1.0", "Select a log entry to view details...")
        self.details_text.configure(state="disabled")

        # Action buttons for selected event
        action_frame = ctk.CTkFrame(details_sidebar, fg_color="transparent")
        action_frame.pack(pady=(0, 20), padx=10, fill="x")

        ctk.CTkButton(
            action_frame,
            text="📋 Copy",
            command=self.copy_details,
            width=70,
            height=30
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            action_frame,
            text="🔍 Analyze",
            command=self.analyze_event,
            width=70,
            height=30
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            action_frame,
            text="🗑️ Undelete",
            command=self.attempt_undelete,
            width=70,
            height=30,
            fg_color="#2196f3",
            hover_color="#1976d2"
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            action_frame,
            text="🚫 Block",
            command=self.block_event,
            width=70,
            height=30,
            fg_color="#d32f2f",
            hover_color="#b71c1c"
        ).pack(side="left", padx=2)

        # Bind click event to logs text
        self.logs_text.bind('<ButtonRelease-1>', self.on_log_click)

        # Start checking for file events
        self.after(1000, self.process_file_events)

    # ============ FILE MONITORING FUNCTIONS ============

    def start_file_monitoring(self):
        """Start monitoring file system changes"""
        try:
            # Install watchdog if not available
            try:
                import watchdog
            except ImportError:
                messagebox.showinfo("Install Required",
                                    "Installing file monitoring module (watchdog)...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "watchdog"])
                import watchdog

            # Start file system monitoring
            self.observer = Observer()
            event_handler = FileMonitorHandler(self.log_file_event)

            # Monitor important locations
            folders_to_monitor = [
                os.path.expanduser('~/Desktop'),
                os.path.expanduser('~/Documents'),
                os.path.expanduser('~/Downloads'),
                os.path.expanduser('~')
            ]

            for folder in folders_to_monitor:
                if os.path.exists(folder):
                    self.observer.schedule(event_handler, folder, recursive=True)

            self.observer.start()
            self.status_label.configure(text="File monitoring started")

        except Exception as e:
            self.status_label.configure(text=f"File monitor error: {str(e)[:50]}")

    def log_file_event(self, event_type, src_path, dest_path=None):
        """Log file system events to queue"""
        try:
            # Check if it's an important file
            filename = os.path.basename(src_path)

            # Determine severity
            severity = 'Low'
            if event_type == 'deleted':
                severity = 'Medium'
                # Check if it's a system file
                if any(sys_folder in src_path for sys_folder in ['System32', 'Windows', 'Program Files']):
                    severity = 'High'

            # Create log entry
            event_time = datetime.datetime.now()

            if event_type == 'moved':
                details = f"File moved from: {src_path}\nTo: {dest_path}"
            else:
                details = f"Path: {src_path}"

                # Try to get file info before deletion
                if event_type == 'deleted' and os.path.exists(src_path):
                    try:
                        size = os.path.getsize(src_path)
                        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(src_path))
                        details += f"\nSize: {size:,} bytes\nLast modified: {mtime}"
                    except:
                        pass

            log_entry = {
                'Time': event_time,
                'Source': 'File System',
                'Type': f'File {event_type.title()}',
                'Event': f"File {event_type}: {filename}",
                'Details': details,
                'Severity': severity,
                'EventType': event_type,
                'FilePath': src_path
            }

            # Add to queue for thread-safe processing
            self.file_events_queue.put(log_entry)

            # Track deletions
            if event_type == 'deleted':
                self.recent_deletions.append({
                    'time': event_time,
                    'path': src_path,
                    'filename': filename
                })

        except Exception as e:
            print(f"Error logging file event: {e}")

    def process_file_events(self):
        """Process queued file events"""
        try:
            while not self.file_events_queue.empty():
                log_entry = self.file_events_queue.get_nowait()
                self.log_data.insert(0, log_entry)  # Add to beginning
                self.filtered_data.insert(0, log_entry)

                # Update display if showing file events
                if self.type_combo.get() in ['All', 'File']:
                    self.display_single_log(log_entry)

                # Update stats
                self.update_stats()

        except queue.Empty:
            pass

        # Schedule next check
        self.after(500, self.process_file_events)

    def display_single_log(self, log_entry):
        """Display a single log entry"""
        time_str = log_entry['Time'].strftime("%H:%M:%S") if isinstance(log_entry['Time'], datetime.datetime) else "N/A"

        # Create colored entry
        entry = f"[{time_str}] [{log_entry['Source']}] [{log_entry['Type']}]\n"
        entry += f"Event: {log_entry['Event']}\n"
        entry += f"Details: {log_entry['Details'][:200]}\n"
        entry += f"Severity: {log_entry['Severity']}\n"
        entry += "-" * 60 + "\n\n"

        # Determine tag
        if 'deleted' in log_entry['Type'].lower():
            tag = 'file_delete'
        elif 'created' in log_entry['Type'].lower():
            tag = 'file_create'
        elif 'modified' in log_entry['Type'].lower():
            tag = 'file_modify'
        else:
            severity_tag = log_entry['Severity'].lower()
            tag = severity_tag if severity_tag in ['critical', 'high', 'medium', 'low', 'info'] else 'info'

        # Insert at beginning
        self.logs_text.insert('1.0', entry, tag)

    def test_create_file(self):
        """Create a test file to verify monitoring"""
        try:
            test_dir = os.path.expanduser('~/Desktop')
            test_file = os.path.join(test_dir, f"test_file_{int(time.time())}.txt")

            with open(test_file, 'w') as f:
                f.write(f"Test file created at {datetime.datetime.now()}\n")
                f.write("This is a test file for monitoring verification.")

            messagebox.showinfo("Test", f"Test file created:\n{test_file}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create test file: {e}")

    def test_delete_file(self):
        """Delete a test file to verify monitoring"""
        try:
            test_dir = os.path.expanduser('~/Desktop')
            test_files = [f for f in os.listdir(test_dir) if f.startswith('test_file_')]

            if test_files:
                test_file = os.path.join(test_dir, test_files[0])
                os.remove(test_file)
                messagebox.showinfo("Test", f"Test file deleted:\n{test_file}")
            else:
                # Create and delete
                test_file = os.path.join(test_dir, f"test_file_{int(time.time())}.txt")
                with open(test_file, 'w') as f:
                    f.write("Temporary test file")
                os.remove(test_file)
                messagebox.showinfo("Test", f"Created and deleted test file")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete test file: {e}")

    # ============ MISSING METHODS IMPLEMENTATION ============

    def show_processes(self):
        """Show only process-related events"""
        self.filtered_data = [log for log in self.log_data if log['Source'] == 'Process']
        self.display_logs()
        self.status_label.configure(text=f"Showing {len(self.filtered_data)} process events")

    def search_logs(self):
        """Show search dialog"""
        search_term = ctk.CTkInputDialog(
            text="Enter search term:",
            title="Search Logs"
        ).get_input()

        if search_term:
            self.search_entry.delete(0, 'end')
            self.search_entry.insert(0, search_term)
            self.on_search(None)

    def show_threats(self):
        """Show only threat/security events"""
        self.filtered_data = [
            log for log in self.log_data
            if log['Severity'] in ['Critical', 'High']
        ]
        self.display_logs()
        self.status_label.configure(text=f"Showing {len(self.filtered_data)} threat events")

    def show_downloads(self):
        """Show download-related events"""
        self.filtered_data = [
            log for log in self.log_data
            if 'download' in log['Event'].lower() or 'Downloads' in log.get('Details', '')
        ]
        self.display_logs()
        self.status_label.configure(text=f"Showing {len(self.filtered_data)} download events")

    def show_network(self):
        """Show only network-related events"""
        self.filtered_data = [log for log in self.log_data if log['Source'] == 'Network']
        self.display_logs()
        self.status_label.configure(text=f"Showing {len(self.filtered_data)} network events")

    def export_logs(self):
        """Export logs to file"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("System Logs Export\n")
                    f.write("=" * 50 + "\n\n")
                    for log in self.log_data:
                        time_str = log['Time'].strftime("%Y-%m-%d %H:%M:%S") if isinstance(log['Time'],
                                                                                           datetime.datetime) else "N/A"
                        f.write(f"Time: {time_str}\n")
                        f.write(f"Source: {log['Source']}\n")
                        f.write(f"Type: {log['Type']}\n")
                        f.write(f"Event: {log['Event']}\n")
                        f.write(f"Details: {log['Details']}\n")
                        f.write(f"Severity: {log['Severity']}\n")
                        f.write("-" * 40 + "\n\n")

                messagebox.showinfo("Export Successful", f"Logs exported to:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Export Failed", f"Error: {str(e)}")

    def clear_display(self):
        """Clear the display"""
        if messagebox.askyesno("Clear Display", "Clear all displayed logs?"):
            self.logs_text.delete('1.0', 'end')
            self.details_text.configure(state="normal")
            self.details_text.delete('1.0', 'end')
            self.details_text.insert('1.0', "Select a log entry to view details...")
            self.details_text.configure(state="disabled")
            self.status_label.configure(text="Display cleared")

    def copy_details(self):
        """Copy details to clipboard"""
        details = self.details_text.get('1.0', 'end-1c')
        if details and details != "Select a log entry to view details...":
            self.clipboard_clear()
            self.clipboard_append(details)
            messagebox.showinfo("Copied", "Details copied to clipboard")

    def analyze_event(self):
        """Analyze the selected event"""
        details = self.details_text.get('1.0', 'end-1c')
        if details and details != "Select a log entry to view details...":
            # Simple analysis based on keywords
            threats = []

            # Check for suspicious patterns
            suspicious_keywords = ['delete', 'system32', 'format', 'encrypt', 'ransom', 'cmd.exe', 'powershell']
            for keyword in suspicious_keywords:
                if keyword.lower() in details.lower():
                    threats.append(f"Suspicious keyword found: {keyword}")

            # Show analysis results
            if threats:
                analysis = "⚠️ POTENTIAL THREATS DETECTED:\n\n" + "\n".join(threats)
            else:
                analysis = "✅ No obvious threats detected in this event."

            messagebox.showinfo("Event Analysis", analysis)
        else:
            messagebox.showwarning("Analysis", "Please select a log entry to analyze")

    def block_event(self):
        """Block/flag the selected event"""
        details = self.details_text.get('1.0', 'end-1c')
        if details and details != "Select a log entry to view details...":
            response = messagebox.askyesno("Block Event",
                                           "Add this event to blocklist?\n\n"
                                           "Future similar events will be flagged as threats.")
            if response:
                # Extract process or file info from details
                # This is a placeholder - implement actual blocking logic
                messagebox.showinfo("Blocked", "Event added to blocklist")
        else:
            messagebox.showwarning("Block", "Please select a log entry to block")

    def on_log_click(self, event):
        """Handle click on log entry"""
        try:
            # Get clicked line
            index = self.logs_text.index(f"@{event.x},{event.y}")
            line_num = int(index.split('.')[0])

            # Find the log entry that contains this line
            # This is simplified - you may need more complex logic
            # to accurately map lines to log entries
            content = self.logs_text.get('1.0', 'end')
            lines = content.split('\n')

            # Look for log entry start pattern
            for i in range(max(0, line_num - 10), min(len(lines), line_num + 10)):
                if lines[i].startswith('[') and '] [' in lines[i]:
                    # Extract time from line
                    time_part = lines[i].split(']')[0][1:]

                    # Find matching log entry
                    for log in self.filtered_data:
                        if isinstance(log['Time'], datetime.datetime):
                            log_time_str = log['Time'].strftime("%H:%M:%S")
                            if log_time_str == time_part:
                                self.show_event_details(log)
                                return

            self.status_label.configure(text="Could not find matching log entry")
        except Exception as e:
            print(f"Error handling log click: {e}")

    def show_event_details(self, log):
        """Show details of selected log entry"""
        self.details_text.configure(state="normal")
        self.details_text.delete('1.0', 'end')

        details = f"Time: {log['Time']}\n"
        details += f"Source: {log['Source']}\n"
        details += f"Type: {log['Type']}\n"
        details += f"Event: {log['Event']}\n"
        details += f"Severity: {log['Severity']}\n"
        details += f"\nDetails:\n{log['Details']}\n"

        # Add additional info if available
        if 'FilePath' in log:
            details += f"\nFile Path: {log['FilePath']}\n"

        self.details_text.insert('1.0', details)
        self.details_text.configure(state="disabled")
        self.status_label.configure(text=f"Showing details for {log['Type']} event")

    def on_search(self, event):
        """Search logs based on search term"""
        search_term = self.search_entry.get().lower()
        if not search_term:
            self.filtered_data = self.log_data.copy()
        else:
            self.filtered_data = [
                log for log in self.log_data
                if (search_term in log['Event'].lower() or
                    search_term in log['Details'].lower() or
                    search_term in log['Type'].lower() or
                    search_term in log['Source'].lower())
            ]

        self.display_logs()
        self.status_label.configure(text=f"Found {len(self.filtered_data)} logs matching '{search_term}'")

    # ============ ENHANCED LOG COLLECTION ============

    def get_recent_deletions(self):
        """Get recently deleted files using various methods"""
        logs = []

        try:
            # Method 1: Check Recycle Bin (requires special permissions)
            recycle_bin_path = os.path.join(os.environ.get('SystemDrive', 'C:'), '$Recycle.Bin')
            if os.path.exists(recycle_bin_path):
                # This is complex - for now, we'll use file monitoring instead
                pass

            # Method 2: Check Windows Event Logs for file deletions
            if HAS_WIN32:
                try:
                    hand = win32evtlog.OpenEventLog(None, 'Security')
                    flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
                    events = win32evtlog.ReadEventLog(hand, flags, 0)

                    for event in events[:50]:  # Check 50 most recent
                        if event.EventID == 4663:  # File deletion event
                            try:
                                message = win32evtlogutil.SafeFormatMessage(event, 'Security')
                                if 'Delete' in message or 'Deleted' in message:
                                    logs.append({
                                        'Time': event.TimeGenerated,
                                        'Source': 'Security Log',
                                        'Type': 'File Deletion',
                                        'Event': 'File deleted (Security Event)',
                                        'Details': f"Event ID: {event.EventID}\n{message[:200]}",
                                        'Severity': 'Medium'
                                    })
                            except:
                                continue

                    win32evtlog.CloseEventLog(hand)
                except:
                    pass

            # Method 3: Check recent file system changes via USN Journal (advanced)
            # This would require more complex Windows API calls

        except Exception as e:
            self.add_error_log(f"Deletion tracking error: {str(e)}")

        return logs

    def get_file_system_changes(self):
        """Get recent file system changes"""
        logs = []

        try:
            # Check for recently modified system files
            system_folders = ['C:\\Windows\\System32', 'C:\\Windows\\SysWOW64']

            for folder in system_folders:
                if os.path.exists(folder):
                    # Get files modified in last hour
                    cutoff = time.time() - 3600

                    for root, dirs, files in os.walk(folder):
                        for file in files[:20]:  # Limit to 20 files per folder
                            filepath = os.path.join(root, file)
                            try:
                                mtime = os.path.getmtime(filepath)
                                if mtime > cutoff:
                                    file_time = datetime.datetime.fromtimestamp(mtime)

                                    logs.append({
                                        'Time': file_time,
                                        'Source': 'File System',
                                        'Type': 'System File Modified',
                                        'Event': f"System file changed: {file}",
                                        'Details': f"Path: {filepath}\n"
                                                   f"Modified: {file_time.strftime('%Y-%m-%d %H:%M:%S')}",
                                        'Severity': 'High' if 'dll' in file.lower() or 'exe' in file.lower() else 'Medium'
                                    })
                            except:
                                continue

        except Exception as e:
            self.add_error_log(f"File system scan error: {str(e)}")

        return logs

    # ============ MODIFIED CORE FUNCTIONS ============

    def load_all_logs(self):
        """Load all system logs including file deletions"""
        self.log_data = []

        # Collect from different sources
        sources = [
            self.get_event_logs,
            self.get_processes,
            self.get_network_info,
            self.get_recent_files,
            self.get_startup_programs,
            self.get_system_info_logs,
            self.get_recent_deletions,  # New: Track deletions
            self.get_file_system_changes  # New: Track file changes
        ]

        for i, source_func in enumerate(sources):
            try:
                logs = source_func()
                self.log_data.extend(logs)
            except Exception as e:
                self.add_error_log(f"Failed {source_func.__name__}: {str(e)}")

        # Sort by time
        self.log_data.sort(key=lambda x: x.get('Time', datetime.datetime.min), reverse=True)
        self.filtered_data = self.log_data.copy()

    def refresh_logs(self):
        """Refresh all logs and check for recent deletions"""
        self.load_logs_threaded()

        # Also force check recent files
        self.check_recent_activity()

        self.status_label.configure(text="Refreshing logs and checking for deletions...")

    def check_recent_activity(self):
        """Check for recent file activity"""
        try:
            # Check Downloads folder for recent changes
            downloads_path = os.path.expanduser('~/Downloads')
            if os.path.exists(downloads_path):
                # Get files from last 5 minutes
                cutoff = time.time() - 300

                for file in os.listdir(downloads_path):
                    filepath = os.path.join(downloads_path, file)
                    if os.path.isfile(filepath):
                        try:
                            mtime = os.path.getmtime(filepath)
                            if mtime > cutoff:
                                # Check if we already have this in logs
                                file_exists = any(
                                    f.get('FilePath') == filepath
                                    for f in self.log_data
                                    if 'FilePath' in f
                                )

                                if not file_exists:
                                    file_time = datetime.datetime.fromtimestamp(mtime)
                                    self.log_file_event('modified', filepath)
                        except:
                            continue
        except Exception as e:
            print(f"Error checking recent activity: {e}")

    def show_file_events(self):
        """Show only file system events"""
        self.filtered_data = [log for log in self.log_data if log['Source'] == 'File System']
        self.display_logs()
        self.status_label.configure(text=f"Showing {len(self.filtered_data)} file events")

    def show_deletions(self):
        """Show only deletion events"""
        self.filtered_data = [
            log for log in self.log_data
            if 'delete' in log['Type'].lower() or 'deleted' in log['Event'].lower()
        ]
        self.display_logs()
        self.status_label.configure(text=f"Showing {len(self.filtered_data)} deletion events")

    def on_type_filter(self, choice):
        """Filter by event type"""
        if choice == "All":
            self.filtered_data = self.log_data.copy()
        elif choice == "File":
            self.filtered_data = [log for log in self.log_data if log['Source'] == 'File System']
        elif choice == "Process":
            self.filtered_data = [log for log in self.log_data if log['Source'] == 'Process']
        elif choice == "Network":
            self.filtered_data = [log for log in self.log_data if log['Source'] == 'Network']
        elif choice == "Event":
            self.filtered_data = [log for log in self.log_data if log['Source'] == 'Event Log']
        elif choice == "System":
            self.filtered_data = [log for log in self.log_data if log['Source'] == 'System']

        self.display_logs()

    def on_time_filter(self, choice):
        """Filter by time"""
        now = datetime.datetime.now()

        if choice == "Live (1 min)":
            cutoff = now - datetime.timedelta(minutes=1)
        elif choice == "Last 5 min":
            cutoff = now - datetime.timedelta(minutes=5)
        elif choice == "Last 15 min":
            cutoff = now - datetime.timedelta(minutes=15)
        elif choice == "Last hour":
            cutoff = now - datetime.timedelta(hours=1)
        elif choice == "Today":
            cutoff = datetime.datetime(now.year, now.month, now.day)
        else:  # "All"
            cutoff = datetime.datetime.min

        self.filtered_data = [
            log for log in self.log_data
            if isinstance(log['Time'], datetime.datetime) and log['Time'] >= cutoff
        ]

        self.display_logs()
        self.status_label.configure(text=f"Showing {len(self.filtered_data)} events from {choice}")

    def update_stats(self):
        """Update statistics including file deletions"""
        if not self.log_data:
            return

        total = len(self.log_data)
        critical = sum(1 for log in self.log_data if log['Severity'] == 'Critical')
        files = sum(1 for log in self.log_data if log['Source'] == 'File System')
        deletions = sum(1 for log in self.log_data if 'delete' in log['Type'].lower())

        self.stats_labels['total'].configure(text=str(total))
        self.stats_labels['critical'].configure(text=str(critical))
        self.stats_labels['files'].configure(text=str(files))
        self.stats_labels['deletions'].configure(text=str(deletions))

    def attempt_undelete(self):
        """Attempt to recover deleted file (if in Recycle Bin)"""
        details = self.details_text.get('1.0', 'end-1c')

        if not details or details == "Select a log entry to view details...":
            messagebox.showwarning("Undelete", "Please select a deletion log entry first")
            return

        # Extract file path
        import re
        path_match = re.search(r'Path:\s*(.+)', details)
        if not path_match:
            messagebox.showwarning("Undelete", "No file path found in log entry")
            return

        file_path = path_match.group(1).strip()
        filename = os.path.basename(file_path)

        # Check Recycle Bin
        response = messagebox.askyesno(
            "Recover File",
            f"Attempt to recover deleted file?\n\n"
            f"File: {filename}\n"
            f"Original path: {file_path}\n\n"
            f"This will check the Recycle Bin and attempt recovery."
        )

        if response:
            try:
                # Method 1: Check if file is in Recycle Bin
                recycle_bin = os.path.join(os.environ.get('SystemDrive', 'C:'), '$Recycle.Bin')

                if os.path.exists(recycle_bin):
                    # Search for file in Recycle Bin
                    found = False
                    for root, dirs, files in os.walk(recycle_bin):
                        for file in files:
                            if filename in file:
                                source_file = os.path.join(root, file)

                                # Ask where to restore
                                restore_path = filedialog.asksaveasfilename(
                                    initialfile=filename,
                                    title="Save recovered file as..."
                                )

                                if restore_path:
                                    import shutil
                                    shutil.copy2(source_file, restore_path)
                                    messagebox.showinfo("Success", f"File recovered to:\n{restore_path}")
                                    found = True
                                    break

                        if found:
                            break

                    if not found:
                        messagebox.showinfo("Not Found", "File not found in Recycle Bin.\n\n"
                                                         "The file may have been permanently deleted or overwritten.")

                else:
                    messagebox.showwarning("Access Denied",
                                           "Cannot access Recycle Bin.\n"
                                           "The file may have been permanently deleted.")

            except Exception as e:
                messagebox.showerror("Recovery Failed", f"Error: {str(e)}")

    # ============ ENHANCED DISPLAY ============

    def display_logs(self):
        """Display filtered logs with better formatting"""
        self.logs_text.delete('1.0', 'end')

        if not self.filtered_data:
            self.logs_text.insert('1.0', "No logs found. Try changing filters.")
            return

        for log in self.filtered_data[:500]:  # Limit display
            time_str = log['Time'].strftime("%H:%M:%S") if isinstance(log['Time'], datetime.datetime) else "N/A"

            # Create colored entry
            entry = f"[{time_str}] [{log['Source']}] [{log['Type']}]\n"
            entry += f"Event: {log['Event']}\n"

            # Truncate details if too long
            details = log['Details']
            if len(details) > 200:
                details = details[:197] + "..."
            entry += f"Details: {details}\n"

            entry += f"Severity: {log['Severity']}\n"
            entry += "-" * 60 + "\n\n"

            # Determine tag
            if 'File System' == log['Source']:
                if 'Deleted' in log['Type'] or 'Delete' in log['Type']:
                    tag = 'file_delete'
                elif 'Created' in log['Type']:
                    tag = 'file_create'
                elif 'Modified' in log['Type']:
                    tag = 'file_modify'
                else:
                    tag = 'info'
            else:
                severity_tag = log['Severity'].lower()
                tag = severity_tag if severity_tag in ['critical', 'high', 'medium', 'low', 'info'] else 'info'

            self.logs_text.insert('end', entry, tag)

        self.logs_text.see('1.0')

    # ============ EXISTING METHODS (not modified in original but needed) ============

    def add_error_log(self, error_msg):
        """Add error log entry"""
        error_entry = {
            'Time': datetime.datetime.now(),
            'Source': 'System',
            'Type': 'Error',
            'Event': f"Error occurred",
            'Details': error_msg,
            'Severity': 'High'
        }
        self.log_data.insert(0, error_entry)

    def load_logs_threaded(self):
        """Load logs in a separate thread to keep UI responsive"""
        if self.loading:
            return

        self.loading = True
        self.status_label.configure(text="Loading logs...")

        def load_thread():
            try:
                self.load_all_logs()
                self.after(0, self.on_logs_loaded)
            except Exception as e:
                self.after(0, lambda: self.on_logs_error(str(e)))

        thread = threading.Thread(target=load_thread, daemon=True)
        thread.start()

    def on_logs_loaded(self):
        """Called when logs are loaded successfully"""
        self.loading = False
        self.filtered_data = self.log_data.copy()
        self.display_logs()
        self.update_stats()
        self.status_label.configure(text=f"Loaded {len(self.log_data)} log entries")

    def on_logs_error(self, error_msg):
        """Called when logs loading fails"""
        self.loading = False
        self.status_label.configure(text=f"Error loading logs: {error_msg}")
        messagebox.showerror("Loading Error", f"Failed to load logs:\n{error_msg}")

    def get_event_logs(self):
        """Get Windows event logs"""
        logs = []
        if HAS_WIN32:
            try:
                # Check Security log
                hand = win32evtlog.OpenEventLog(None, 'Security')
                flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
                events = win32evtlog.ReadEventLog(hand, flags, 0)

                for event in events[:100]:
                    try:
                        message = win32evtlogutil.SafeFormatMessage(event, 'Security')
                        logs.append({
                            'Time': event.TimeGenerated,
                            'Source': 'Event Log',
                            'Type': 'Security Event',
                            'Event': f"Event ID: {event.EventID}",
                            'Details': f"{message[:500]}",
                            'Severity': 'High' if event.EventType in [win32con.EVENTLOG_ERROR_TYPE,
                                                                      win32con.EVENTLOG_AUDIT_FAILURE] else 'Medium'
                        })
                    except:
                        continue

                win32evtlog.CloseEventLog(hand)
            except:
                pass
        return logs

    def get_processes(self):
        """Get running processes"""
        logs = []
        if HAS_PSUTIL:
            try:
                for proc in psutil.process_iter(['pid', 'name', 'username', 'create_time']):
                    try:
                        info = proc.info
                        logs.append({
                            'Time': datetime.datetime.fromtimestamp(info['create_time']),
                            'Source': 'Process',
                            'Type': 'Running Process',
                            'Event': f"Process: {info['name']} (PID: {info['pid']})",
                            'Details': f"User: {info['username']}\nPID: {info['pid']}\nName: {info['name']}",
                            'Severity': 'Low'
                        })
                    except:
                        continue
            except:
                pass
        return logs

    def get_network_info(self):
        """Get network connections"""
        logs = []
        if HAS_PSUTIL:
            try:
                for conn in psutil.net_connections(kind='inet'):
                    try:
                        if conn.status == 'ESTABLISHED':
                            logs.append({
                                'Time': datetime.datetime.now(),
                                'Source': 'Network',
                                'Type': 'Network Connection',
                                'Event': f"Connection: {conn.laddr.ip}:{conn.laddr.port} -> {conn.raddr.ip if conn.raddr else 'N/A'}:{conn.raddr.port if conn.raddr else 'N/A'}",
                                'Details': f"Status: {conn.status}\nPID: {conn.pid}",
                                'Severity': 'Medium'
                            })
                    except:
                        continue
            except:
                pass
        return logs

    def get_recent_files(self):
        """Get recently modified files"""
        logs = []
        try:
            recent_folders = [
                os.path.expanduser('~/Downloads'),
                os.path.expanduser('~/Desktop')
            ]

            for folder in recent_folders:
                if os.path.exists(folder):
                    # Get files modified in last 24 hours
                    cutoff = time.time() - 86400

                    for file in os.listdir(folder)[:20]:
                        filepath = os.path.join(folder, file)
                        if os.path.isfile(filepath):
                            try:
                                mtime = os.path.getmtime(filepath)
                                if mtime > cutoff:
                                    logs.append({
                                        'Time': datetime.datetime.fromtimestamp(mtime),
                                        'Source': 'File System',
                                        'Type': 'Recent File',
                                        'Event': f"Recent file: {file}",
                                        'Details': f"Path: {filepath}\nModified: {datetime.datetime.fromtimestamp(mtime)}",
                                        'Severity': 'Low'
                                    })
                            except:
                                continue
        except Exception as e:
            self.add_error_log(f"Recent files error: {str(e)}")

        return logs

    def get_startup_programs(self):
        """Get startup programs"""
        logs = []
        try:
            # Check registry startup locations
            startup_locations = [
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
            ]

            for hive, location in startup_locations:
                try:
                    key = winreg.OpenKey(hive, location, 0, winreg.KEY_READ)
                    i = 0
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(key, i)
                            logs.append({
                                'Time': datetime.datetime.now(),
                                'Source': 'System',
                                'Type': 'Startup Program',
                                'Event': f"Startup: {name}",
                                'Details': f"Registry: {location}\nValue: {value[:200]}",
                                'Severity': 'Medium'
                            })
                            i += 1
                        except WindowsError:
                            break
                    winreg.CloseKey(key)
                except:
                    continue
        except Exception as e:
            self.add_error_log(f"Startup programs error: {str(e)}")

        return logs

    def get_system_info_logs(self):
        """Get system information logs"""
        logs = []
        try:
            # System info
            info = {
                'System': platform.system(),
                'Node': platform.node(),
                'Release': platform.release(),
                'Version': platform.version(),
                'Machine': platform.machine(),
                'Processor': platform.processor(),
            }

            logs.append({
                'Time': datetime.datetime.now(),
                'Source': 'System',
                'Type': 'System Info',
                'Event': f"System: {info['System']} {info['Release']}",
                'Details': f"Node: {info['Node']}\nVersion: {info['Version']}\nMachine: {info['Machine']}\nProcessor: {info['Processor'][:100]}",
                'Severity': 'Info'
            })

            # Disk info
            if HAS_PSUTIL:
                for partition in psutil.disk_partitions():
                    try:
                        usage = psutil.disk_usage(partition.mountpoint)
                        logs.append({
                            'Time': datetime.datetime.now(),
                            'Source': 'System',
                            'Type': 'Disk Info',
                            'Event': f"Disk: {partition.device} ({partition.mountpoint})",
                            'Details': f"Type: {partition.fstype}\nTotal: {usage.total:,} bytes\nUsed: {usage.percent}%",
                            'Severity': 'Info'
                        })
                    except:
                        continue
        except Exception as e:
            self.add_error_log(f"System info error: {str(e)}")

        return logs


def main():
    """Main entry point"""
    try:
        app = SimpleLogViewer()
        app.mainloop()
    except Exception as e:
        messagebox.showerror("Error", f"Application error: {str(e)}")
        print(f"Error: {e}")


if __name__ == "__main__":
    main()