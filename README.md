# System Activity Monitor with File Tracking

![System Monitor](https://img.shields.io/badge/System-Monitor-blue)
![Python](https://img.shields.io/badge/Python-3.8%2B-green)
![Windows](https://img.shields.io/badge/Platform-Windows-orange)
![Admin](https://img.shields.io/badge/Requires-Admin%20Privileges-red)

A comprehensive system monitoring tool with real-time file tracking, process monitoring, and security event logging for Windows systems.

## 🚀 Features

### 📁 **File System Monitoring**
- Real-time tracking of file creations, deletions, modifications, and moves
- Monitors important folders (Desktop, Documents, Downloads, System32, etc.)
- Tracks recently deleted files with recovery attempts
- File change severity classification

### ⚙️ **System Monitoring**
- Process monitoring and analysis
- Windows Event Log collection
- Network connection tracking
- Startup program detection
- System information gathering

### 🔍 **Security Features**
- Threat detection based on event patterns
- Suspicious activity alerts
- Event analysis and risk assessment
- Custom blocklists for events

### 🎨 **User Interface**
- Modern dark theme interface using CustomTkinter
- Real-time log display with color-coded severity
- Quick statistics dashboard
- Advanced filtering options
- Detailed event inspection panel

## 📦 Installation

### Prerequisites
- Windows 7/8/10/11 (64-bit recommended)
- Python 3.8 or higher
- Administrator privileges

### Quick Install
```bash
# Clone or download the project
git clone https://github.com/yourusername/system-activity-monitor.git
cd system-activity-monitor

# Install dependencies
pip install -r requirements.txt
```

### Manual Installation
```bash
# Install required packages
pip install customtkinter
pip install watchdog
pip install psutil
pip install pywin32
pip install pillow
```

## 🏃‍♂️ Usage

### Running the Application
```bash
python main.py
```

**Note:** The application will request administrator privileges on startup, which are required for proper system monitoring.

### Main Interface Components

#### 1. **Sidebar Actions**
- 🔄 **Refresh**: Reload all logs and check for recent activity
- 📊 **Processes**: Show only process-related events
- 📁 **File Monitor**: Show file system events
- 🗑️ **Deletions**: Show file deletion events
- 🔍 **Search**: Search through logs
- ⚠️ **Threats**: Show high-severity events
- 📥 **Downloads**: Show download-related events
- 🔗 **Network**: Show network connection events
- 💾 **Export**: Export logs to file
- 🧹 **Clear**: Clear the display

#### 2. **Quick Statistics**
- **Total**: Total number of log entries
- **Critical**: Number of critical severity events
- **Files**: Number of file system events
- **Deletions**: Number of file deletion events

#### 3. **Filters**
- **Time Filter**: Live (1 min), Last 5 min, Last 15 min, Last hour, Today, All
- **Type Filter**: All, File, Process, Network, Event, System
- **Search**: Real-time text search across all logs

#### 4. **Event Details Panel**
- View detailed information about selected events
- Copy event details to clipboard
- Analyze events for threats
- Attempt file recovery (undelete)
- Block suspicious events

## 🔧 Building Executable

### Using PyInstaller (Recommended)
```bash
# Install PyInstaller
pip install pyinstaller

# Build executable
pyinstaller --onefile --windowed --name="SystemMonitor" ^
  --hidden-import=tkinter --hidden-import=customtkinter ^
  --hidden-import=watchdog --hidden-import=psutil ^
  --hidden-import=win32evtlog --hidden-import=win32evtlogutil ^
  --collect-all=customtkinter --collect-all=watchdog ^
  main.py
```

### Using auto-py-to-exe (GUI)
```bash
# Install auto-py-to-exe
pip install auto-py-to-exe

# Launch the GUI
auto-py-to-exe
```

**Settings for auto-py-to-exe:**
- Script Location: `main.py`
- One File: ✓ Checked
- Console Window: Window Based (hide the console)
- Additional Files: Add CustomTkinter and watchdog folders
- Hidden Imports: Add all packages from the PyInstaller command above

## 📝 Features in Detail

### File Monitoring
- Monitors key system folders and user directories
- Detects file operations in real-time
- Classifies events by severity
- Tracks file metadata before deletion

### Process Tracking
- Lists all running processes
- Shows process creation time and user
- Identifies suspicious process behavior

### Security Features
- Analyzes events for security threats
- Flags suspicious file modifications
- Identifies unauthorized access attempts
- Provides event blocking capabilities

### Log Management
- Collects logs from multiple sources
- Advanced filtering and searching
- Export functionality for analysis
- Real-time updates

## 🛠️ Technical Details

### Architecture
- **Frontend**: CustomTkinter for modern UI
- **Monitoring**: watchdog for file system events
- **System Info**: psutil for process and system data
- **Windows Integration**: pywin32 for event logs
- **Threading**: Separate threads for monitoring and UI

### File Structure
```
system-monitor/
├── main.py                 # Main application file
├── requirements.txt        # Dependencies list
├── README.md              # This file
├── build_exe.py           # Build script for executable
├── icon.ico               # Application icon (optional)
└── admin_manifest.xml     # Admin privileges manifest
```

### Dependencies
```txt
customtkinter>=5.2.0
watchdog>=3.0.0
psutil>=5.9.0
pywin32>=305
Pillow>=10.0.0
```

## ⚠️ Important Notes

### Administrator Privileges
This tool **requires** administrator privileges to:
- Access Windows Event Logs
- Monitor system folders
- Track all running processes
- Access security event information

The application will automatically request elevation if not run as administrator.

### Security Considerations
- The tool monitors sensitive system information
- Use responsibly and only on systems you own or manage
- Export logs contain potentially sensitive information
- File recovery attempts may not work for permanently deleted files

### Limitations
- Windows-only application
- Requires .NET Framework 4.5+ (usually pre-installed)
- Some features require specific Windows versions
- File recovery depends on Recycle Bin availability

## 🔒 Privacy and Security

### Data Collection
The application collects:
- File system event logs
- Process information
- Network connection data
- Windows Event Logs
- System information

### Data Storage
- Logs are stored in memory during runtime
- Export files contain collected log data
- No data is transmitted externally
- All processing is done locally

## 🐛 Troubleshooting

### Common Issues

1. **"No module named 'customtkinter'"**
   ```bash
   pip install customtkinter
   ```

2. **Admin privileges not granted**
   - Right-click → "Run as administrator"
   - Check UAC settings

3. **File monitoring not working**
   - Ensure watchdog is installed: `pip install watchdog`
   - Check folder permissions

4. **Process information missing**
   - Install psutil: `pip install psutil`
   - Run as administrator

5. **Event logs inaccessible**
   - Install pywin32: `pip install pywin32`
   - Run as administrator

### Debug Mode
```bash
# Run with console for debugging
python main.py 2> debug.log
```

## 📄 License

This project is provided for educational and legitimate monitoring purposes only.

**⚠️ DISCLAIMER:** 
- Use only on systems you own or have explicit permission to monitor
- Comply with all applicable laws and regulations
- The authors are not responsible for misuse of this software

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📞 Support

For issues, questions, or feature requests:
1. Check the Troubleshooting section
2. Open an issue on GitHub
3. Provide detailed information about the problem

---

**Remember:** With great power comes great responsibility. Use this tool ethically and legally.
