#!/usr/bin/env bash
# crash-evidence.sh — after an unexplained reboot, print what Windows recorded about it, so every crash is logged the same
# way (crash log and hypotheses: hw-upgrade-july-2026.md, "Crash log"). WSL only (reads the Windows event log).
#
# Usage: hwmonitor/crash-evidence.sh [N]   the last N unexpected shutdowns (Kernel-Power 41), default 1
set -uo pipefail
n=${1:-1}
powershell.exe -NoProfile -Command "
\$crashes = Get-WinEvent -FilterHashtable @{LogName='System'; Id=41} -MaxEvents $n
foreach (\$c in \$crashes) {
  \$d = @{}; ([xml]\$c.ToXml()).Event.EventData.Data | ForEach-Object { \$d[\$_.Name] = \$_.'#text' }
  \$boot = \$c.TimeCreated
  \$last = Get-WinEvent -FilterHashtable @{LogName='System','Application'; EndTime=\$boot.AddSeconds(-30); StartTime=\$boot.AddHours(-2)} -MaxEvents 1 -ErrorAction SilentlyContinue
  '=== boot after crash: {0}' -f \$boot
  '  BugcheckCode {0} (0 = no bugcheck: power loss, hard hang or reset)  Param1 {1}  PowerButtonTimestamp {2}  SleepInProgress {3}' -f \$d.BugcheckCode, \$d.BugcheckParameter1, \$d.PowerButtonTimestamp, \$d.SleepInProgress
  if (\$last) { '  last event logged before it: {0}  (gap to boot {1:N1} min: ~1 = reset by itself, longer = froze or off until reset by hand)' -f \$last.TimeCreated, (\$boot - \$last.TimeCreated).TotalMinutes; \$from = \$last.TimeCreated }
  else { '  no event logged in the 2 h before'; \$from = \$boot.AddMinutes(-30) }
  '  WHEA in the 24 h before:'; Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-WHEA-Logger'; StartTime=\$boot.AddHours(-24); EndTime=\$boot} -ErrorAction SilentlyContinue | ForEach-Object { '    {0} {1}' -f \$_.TimeCreated, \$_.Id }
  '  GPU driver events (nvlddmkm) in the 24 h before:'; Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='nvlddmkm'; StartTime=\$boot.AddHours(-24); EndTime=\$boot} -ErrorAction SilentlyContinue | Group-Object Id | ForEach-Object { '    id {0}: {1}x' -f \$_.Name, \$_.Count }
  '  warnings/errors in the 20 min before:'; Get-WinEvent -FilterHashtable @{LogName='System','Application'; Level=1,2,3; StartTime=\$from.AddMinutes(-20); EndTime=\$boot} -ErrorAction SilentlyContinue | ForEach-Object { '    {0} {1} {2}' -f \$_.TimeCreated, \$_.Id, \$_.ProviderName }
  '  dumps written:'; Get-ChildItem C:\Windows\Minidump -ErrorAction SilentlyContinue | Where-Object { [math]::Abs((\$_.LastWriteTime - \$boot).TotalMinutes) -lt 15 } | ForEach-Object { '    ' + \$_.FullName }
}
'=== now: RAM'; Get-CimInstance Win32_PhysicalMemory | ForEach-Object { '  {0} GB {1} configured {2} MT/s (JEDEC {3})' -f (\$_.Capacity/1GB), \$_.PartNumber.Trim(), \$_.ConfiguredClockSpeed, \$_.Speed }
'  BIOS ' + (Get-CimInstance Win32_BIOS).SMBIOSBIOSVersion
" 2>&1 | tr -d '\r'
echo "  GPU power limits now: $(nvidia-smi --query-gpu=power.limit --format=csv,noheader | paste -sd/ -) (reset to default by a reboot)"
echo "Add what this cannot see to the crash log: the workload at the time, whether the screen froze or the PC restarted"
echo "by itself, temperatures if hwmonitor was running, and anything changed since the last crash (BIOS, driver, EXPO)."
