using System;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Text.Json;

namespace MimobotControlCenter
{
    public class OBSService
    {
        private ClientWebSocket? _ws;
        private string _url = "ws://127.0.0.1:4455"; 

        public OBSService()
        {
            _ = ConnectToOBS();
        }

        private async Task ConnectToOBS()
        {
            try {
                _ws = new ClientWebSocket();
                await _ws.ConnectAsync(new Uri(_url), CancellationToken.None);
                Console.WriteLine("OBS Connected!");
            } catch { }
        }

        public async void ExecuteAction(string action)
        {
            if (_ws?.State != WebSocketState.Open) await ConnectToOBS();
            if (_ws?.State != WebSocketState.Open) return;

            string requestType = action switch
            {
                "RECORD_START" => "StartRecord",
                "RECORD_STOP" => "StopRecord",
                "STREAM_START" => "StartStream",
                "STREAM_STOP" => "StopStream",
                "REPLAY_SAVE" => "SaveReplayBuffer",
                "SCENE_SWITCH" => "SetCurrentProgramScene",
                _ => ""
            };

            if (string.IsNullOrEmpty(requestType)) return;

            var request = new
            {
                op = 6, 
                d = new
                {
                    requestType = requestType,
                    requestId = Guid.NewGuid().ToString()
                }
            };

            string jsonString = JsonSerializer.Serialize(request);
            var bytes = Encoding.UTF8.GetBytes(jsonString);
            await _ws.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, CancellationToken.None);
        }
    }
}
