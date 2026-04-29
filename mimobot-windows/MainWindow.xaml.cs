using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Runtime.InteropServices;
using System.Windows.Interop;
using System.Drawing;
using System.Drawing.Imaging;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Text.Json;
using System.Windows.Threading;
using LibreHardwareMonitor.Hardware;

namespace MimobotControlCenter
{
    public class FeatureItem {
        public string Name { get; set; } = "";
        public string Icon { get; set; } = "";
    }

    public partial class MainWindow : Window
    {
        private ClientWebSocket? _ws;
        private Dictionary<int, Dictionary<int, string>> _pageMappings = new Dictionary<int, Dictionary<int, string>>();
        private OBSService _obs = new OBSService();
        private int _currentPage = 1;
        private int _totalPages = 1;

        // --- FEATURES MODE VARIABLES ---
        private bool _inFeaturesMode = false;
        private string _currentFeatureApp = "";
        private Dictionary<string, Dictionary<int, string>> _featureMappings = new Dictionary<string, Dictionary<int, string>>();
        private Dictionary<string, List<string>> _appFeatures = new Dictionary<string, List<string>> {
            { "discord", new List<string> { "Mute", "Deafen", "Voice Channel", "Text Channel", "Push to Talk", "Soundboard" } },
            { "obs", new List<string> { "Record", "Stream", "Virtual Camera", "Replay Buffer", "Scene Switch", "Audio Mixer" } },
            { "photoshop", new List<string> { "Undo/Redo", "Play Action", "Layer Scroll", "Adjust Hue/Sat", "Content-Aware Fill" } }
        };
        
        // UPGRADED TO SEGOE FLUENT ICONS (Professional)
        private Dictionary<string, string> _featureIcons = new Dictionary<string, string> {
            { "Mute", "\xE720" }, { "Deafen", "\xE7F6" }, { "Voice Channel", "\xE767" }, { "Text Channel", "\xE8BD" }, { "Push to Talk", "\xE7C8" }, { "Soundboard", "\xE904" },
            { "Record", "\xE7C8" }, { "Stream", "\xE8B1" }, { "Virtual Camera", "\xE722" }, { "Replay Buffer", "\xE81C" }, { "Scene Switch", "\xE8AB" }, { "Audio Mixer", "\xE9D9" },
            { "Undo/Redo", "\xE7A7" }, { "Play Action", "\xE768" }, { "Layer Scroll", "\xE81E" }, { "Adjust Hue/Sat", "\xE790" }, { "Content-Aware Fill", "\xE946" },
            { "Launch", "\xE768" }, { "Close", "\xE711" }, { "Force Kill", "\xE74D" }, { "Settings", "\xE713" }
        };

        // --- HARDWARE MONITORING ---
        private Computer _computer;
        private DispatcherTimer _telemetryTimer;

        public MainWindow()
        {
            InitializeComponent();
            EnableGlass();
            _pageMappings[1] = new Dictionary<int, string>();
            
            // Initialize Hardware Monitor
            _computer = new Computer { IsCpuEnabled = true, IsGpuEnabled = true, IsMemoryEnabled = true, IsStorageEnabled = true };
            try { _computer.Open(); } catch { }

            _telemetryTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(1) };
            _telemetryTimer.Tick += (s, e) => SendTelemetry();
            _telemetryTimer.Start();

            this.Loaded += (s, e) => { UpdatePagePills(); _ = ConnectToMimobot(); };
        }

        private async void SendTelemetry() {
            float cpu = 0, gpu = 0, ramUsed = 0, disk = 0;
            foreach (var hw in _computer.Hardware) {
                hw.Update();
                if (hw.HardwareType == HardwareType.Cpu) {
                    foreach (var s in hw.Sensors) if (s.SensorType == SensorType.Load && s.Name == "CPU Total") cpu = s.Value ?? 0;
                }
                else if (hw.HardwareType == HardwareType.GpuNvidia || hw.HardwareType == HardwareType.GpuAmd || hw.HardwareType == HardwareType.GpuIntel) {
                    foreach (var s in hw.Sensors) if (s.SensorType == SensorType.Load && s.Name.Contains("Core")) gpu = s.Value ?? 0;
                }
                else if (hw.HardwareType == HardwareType.Memory) {
                    foreach (var s in hw.Sensors) if (s.Name == "Memory Used") ramUsed = s.Value ?? 0;
                }
                else if (hw.HardwareType == HardwareType.Storage) {
                    foreach (var s in hw.Sensors) if (s.SensorType == SensorType.Load && s.Name == "Total Activity") disk = s.Value ?? 0;
                }
            }
            
            // Send exactly what the Pi needs to draw the overlay
            var payload = new {
                type = "TELEMETRY",
                cpu = (int)cpu,
                gpu = (int)gpu,
                ram = $"{ramUsed:F1} GB",
                disk = (int)disk,
                time = DateTime.Now.ToString("HH:mm"),
                date = DateTime.Now.ToString("MMM dd")
            };
            await SendMessage(JsonSerializer.Serialize(payload));
        }

        private async Task ConnectToMimobot() { try { _ws = new ClientWebSocket(); await _ws.ConnectAsync(new Uri("ws://192.168.1.100:8000"), CancellationToken.None); Dispatcher.Invoke(() => { StatusLabel.Text = "● Connected"; StatusLabel.Foreground = System.Windows.Media.Brushes.LightGreen; }); } catch { } }

        // --- DOUBLE CLICK DETECTION ---
        private void Slot_Click(object sender, System.Windows.Input.MouseButtonEventArgs e)
        {
            if (e.ClickCount == 2 && !_inFeaturesMode)
            {
                Border? slot = sender as Border;
                if (slot == null || slot.Tag == null) return;
                int slotIndex = int.Parse(slot.Tag.ToString()!);
                if (_pageMappings[_currentPage].ContainsKey(slotIndex)) {
                    OpenFeaturesMode(_pageMappings[_currentPage][slotIndex]);
                }
            }
        }

        private void OpenFeaturesMode(string appPath)
        {
            _inFeaturesMode = true;
            _currentFeatureApp = appPath;
            if (!_featureMappings.ContainsKey(appPath)) _featureMappings[appPath] = new Dictionary<int, string>();
            
            var color = GetAverageColor(appPath);
            DynamicBackground.Background = new SolidColorBrush(System.Windows.Media.Color.FromArgb(30, color.R, color.G, color.B)); 
            
            string appName = Path.GetFileNameWithoutExtension(appPath).ToLower();
            string key = _appFeatures.Keys.FirstOrDefault(k => appName.Contains(k)) ?? "";
            var list = key != "" ? _appFeatures[key] : new List<string> { "Launch", "Close", "Force Kill", "Settings" };
            FeaturesList.ItemsSource = list.Select(f => new FeatureItem { Name = f, Icon = _featureIcons.ContainsKey(f) ? _featureIcons[f] : "\xE713" }).ToList();
            
            FeaturesPanel.Visibility = Visibility.Visible;
            LoadFeaturePage();
        }

        private void BackToMain_Click(object sender, RoutedEventArgs e)
        {
            _inFeaturesMode = false;
            DynamicBackground.Background = System.Windows.Media.Brushes.Transparent;
            FeaturesPanel.Visibility = Visibility.Collapsed;
            LoadPage(_currentPage);
        }

        private void LoadFeaturePage()
        {
            for (int i = 1; i <= 6; i++) {
                var img = this.FindName($"Img{i}") as System.Windows.Controls.Image;
                var iconTxt = this.FindName($"IconTxt{i}") as TextBlock;
                var txt = this.FindName($"Txt{i}") as TextBlock;
                var border = this.FindName($"Slot{i}") as Border;
                
                if (img != null) img.Visibility = Visibility.Collapsed;
                if (iconTxt != null) iconTxt.Visibility = Visibility.Collapsed;
                if (txt != null) { txt.Text = ""; txt.Visibility = Visibility.Visible; txt.FontWeight = FontWeights.Normal; }
                if (border != null) border.BorderBrush = new SolidColorBrush(System.Windows.Media.Color.FromRgb(51, 51, 51));
                
                if (_featureMappings[_currentFeatureApp].ContainsKey(i)) {
                    string feature = _featureMappings[_currentFeatureApp][i];
                    if (txt != null) { txt.Text = feature; txt.FontWeight = FontWeights.Bold; }
                    if (iconTxt != null) {
                        iconTxt.Text = _featureIcons.ContainsKey(feature) ? _featureIcons[feature] : "\xE713";
                        iconTxt.Visibility = Visibility.Visible;
                    }
                    if (border != null) border.BorderBrush = new SolidColorBrush(System.Windows.Media.Color.FromRgb(0, 163, 255));
                }
            }
        }

        private void FeaturesList_MouseDown(object sender, System.Windows.Input.MouseButtonEventArgs e)
        {
            if (e.OriginalSource is FrameworkElement fe && fe.DataContext is FeatureItem fi) {
                DragDrop.DoDragDrop(FeaturesList, fi.Name, DragDropEffects.Copy);
            }
        }

        private void Slot_Drop(object sender, DragEventArgs e)
        {
            Border? slot = sender as Border;
            if (slot == null || slot.Tag == null) return;
            int slotIndex = int.Parse(slot.Tag.ToString()!);

            if (!_inFeaturesMode && e.Data.GetDataPresent(DataFormats.FileDrop))
            {
                string[] files = (string[])e.Data.GetData(DataFormats.FileDrop);
                if (files.Length > 0)
                {
                    string filePath = files[0];
                    string targetPath = filePath;
                    if (Path.GetExtension(filePath).ToLower() == ".lnk") targetPath = ResolveShortcut(filePath);
                    _pageMappings[_currentPage][slotIndex] = filePath;
                    UpdateSlotUI(slotIndex, filePath, targetPath);
                    ExtractAndSendIcon(slotIndex, targetPath);
                }
            }
            else if (_inFeaturesMode && e.Data.GetDataPresent(DataFormats.StringFormat))
            {
                string feature = e.Data.GetData(DataFormats.StringFormat).ToString()!;
                _featureMappings[_currentFeatureApp][slotIndex] = feature;
                LoadFeaturePage();
            }
        }

        private void UpdateSlotUI(int slotIndex, string originalPath, string iconPath)
        {
            var img = this.FindName($"Img{slotIndex}") as System.Windows.Controls.Image;
            var txt = this.FindName($"Txt{slotIndex}") as TextBlock;
            var border = this.FindName($"Slot{slotIndex}") as Border;
            if (img != null) { img.Source = GetIconSource(iconPath); img.Visibility = Visibility.Visible; }
            if (txt != null) { txt.Text = Path.GetFileNameWithoutExtension(originalPath); txt.Visibility = ToggleLabels.IsChecked == true ? Visibility.Visible : Visibility.Collapsed; txt.FontWeight = FontWeights.Normal; }
            if (border != null) border.BorderBrush = new SolidColorBrush(System.Windows.Media.Color.FromRgb(0, 163, 255));
        }

        private void ClearSlot_Click(object sender, RoutedEventArgs e)
        {
            MenuItem? item = sender as MenuItem;
            ContextMenu? menu = item?.Parent as ContextMenu;
            Border? slot = menu?.PlacementTarget as Border;
            if (slot == null || slot.Tag == null) return;
            int slotIndex = int.Parse(slot.Tag.ToString()!);
            if (_inFeaturesMode) {
                if (_featureMappings[_currentFeatureApp].ContainsKey(slotIndex)) { _featureMappings[_currentFeatureApp].Remove(slotIndex); LoadFeaturePage(); }
            } else {
                if (_pageMappings[_currentPage].ContainsKey(slotIndex)) { _pageMappings[_currentPage].Remove(slotIndex); LoadPage(_currentPage); }
            }
        }

        private void UpdatePagePills()
        {
            if (PagePills == null) return;
            PagePills.Items.Clear();
            for (int i = 1; i <= _totalPages; i++)
            {
                bool isActive = (i == _currentPage);
                Button pill = new Button { 
                    Content = i.ToString(), 
                    Style = (Style)this.Resources["PagePill"],
                    Background = isActive ? new SolidColorBrush(System.Windows.Media.Color.FromRgb(200, 200, 200)) : System.Windows.Media.Brushes.Transparent,
                    Foreground = isActive ? System.Windows.Media.Brushes.Black : new SolidColorBrush(System.Windows.Media.Color.FromRgb(136, 136, 136)),
                    Tag = i, MinWidth = 35 
                };
                pill.Click += (s, e) => { if(!_inFeaturesMode) LoadPage((int)((Button)s).Tag); };
                PagePills.Items.Add(pill);
            }
        }

        private void LoadPage(int pageNum)
        {
            _currentPage = pageNum;
            for (int i = 1; i <= 6; i++) {
                var img = this.FindName($"Img{i}") as System.Windows.Controls.Image;
                var iconTxt = this.FindName($"IconTxt{i}") as TextBlock;
                var txt = this.FindName($"Txt{i}") as TextBlock;
                var border = this.FindName($"Slot{i}") as Border;
                if (img != null) img.Visibility = Visibility.Collapsed;
                if (iconTxt != null) iconTxt.Visibility = Visibility.Collapsed;
                if (txt != null) txt.Text = "";
                if (border != null) border.BorderBrush = new SolidColorBrush(System.Windows.Media.Color.FromRgb(51, 51, 51));
                if (_pageMappings[pageNum].ContainsKey(i)) UpdateSlotUI(i, _pageMappings[pageNum][i], _pageMappings[pageNum][i]);
            }
            UpdatePagePills();
        }

        private System.Windows.Media.Color GetAverageColor(string path) {
            try {
                using (var icon = System.Drawing.Icon.ExtractAssociatedIcon(path))
                using (var bmp = new Bitmap(1, 1))
                using (var g = Graphics.FromImage(bmp)) {
                    g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
                    g.DrawImage(icon!.ToBitmap(), new System.Drawing.Rectangle(0, 0, 1, 1));
                    var c = bmp.GetPixel(0, 0);
                    return System.Windows.Media.Color.FromArgb(255, c.R, c.G, c.B);
                }
            } catch { return System.Windows.Media.Color.FromRgb(30, 30, 30); }
        }

        private void Page_Add_Click(object sender, RoutedEventArgs e) { if(_inFeaturesMode) return; _totalPages++; _pageMappings[_totalPages] = new Dictionary<int, string>(); LoadPage(_totalPages); }
        private void Page_Next_Click(object sender, RoutedEventArgs e) { }
        private void Page_Prev_Click(object sender, RoutedEventArgs e) { }
        private string ResolveShortcut(string lnkPath) { try { Type? t = Type.GetTypeFromProgID("Shell.Application"); dynamic? s = Activator.CreateInstance(t!); var f = s!.NameSpace(Path.GetDirectoryName(lnkPath)); var i = f.ParseName(Path.GetFileName(lnkPath)); return i.GetLink.Path; } catch { return lnkPath; } }
        private ImageSource? GetIconSource(string path) { try { using (var icon = System.Drawing.Icon.ExtractAssociatedIcon(path)) using (var bmp = icon!.ToBitmap()) { IntPtr h = bmp.GetHbitmap(); try { return Imaging.CreateBitmapSourceFromHBitmap(h, IntPtr.Zero, Int32Rect.Empty, System.Windows.Media.Imaging.BitmapSizeOptions.FromEmptyOptions()); } finally { DeleteObject(h); } } } catch { return null; } }
        private void ExtractAndSendIcon(int slot, string path) { try { using (var icon = System.Drawing.Icon.ExtractAssociatedIcon(path)) using (var bmp = icon!.ToBitmap()) { using (MemoryStream ms = new MemoryStream()) { bmp.Save(ms, ImageFormat.Png); _ = SendMessage($"{{\"type\":\"SYNC_ICON\", \"slot\":{slot}, \"icon\":\"{Convert.ToBase64String(ms.ToArray())}\"}}"); } } } catch { } }
        private async Task SendMessage(string msg) { if (_ws?.State == WebSocketState.Open) await _ws.SendAsync(new ArraySegment<byte>(Encoding.UTF8.GetBytes(msg)), WebSocketMessageType.Text, true, CancellationToken.None); }
        [DllImport("dwmapi.dll")] private static extern int DwmSetWindowAttribute(IntPtr h, int a, ref int v, int s);
        [DllImport("gdi32.dll")] public static extern bool DeleteObject(IntPtr h);
        private void EnableGlass() { IntPtr h = new WindowInteropHelper(this).EnsureHandle(); int v = 1; DwmSetWindowAttribute(h, 38, ref v, 4); DwmSetWindowAttribute(h, 20, ref v, 4); }
        private void Pin_Click(object sender, RoutedEventArgs e) { this.Topmost = !this.Topmost; var pinBtn = sender as Button; if (pinBtn != null) pinBtn.Foreground = this.Topmost ? new SolidColorBrush(System.Windows.Media.Color.FromRgb(0, 163, 255)) : new SolidColorBrush(System.Windows.Media.Color.FromRgb(85, 85, 85)); }
        private void Window_Drop(object sender, DragEventArgs e) { }
        private void Help_Click(object sender, RoutedEventArgs e) { HelpOverlay.Visibility = Visibility.Visible; }
        private void Help_Close_Click(object sender, RoutedEventArgs e) { HelpOverlay.Visibility = Visibility.Collapsed; }
        
        private void SyncAll_Click(object sender, RoutedEventArgs e) { MessageBox.Show("Synced!"); }
        private void ToggleLabels_Changed(object sender, RoutedEventArgs e) { if (ToggleLabels == null) return; Visibility v = ToggleLabels.IsChecked == true ? Visibility.Visible : Visibility.Collapsed; for (int i = 1; i <= 6; i++) { var t = this.FindName($"Txt{i}") as TextBlock; if (t != null && !_inFeaturesMode) t.Visibility = v; } }
    }
}
