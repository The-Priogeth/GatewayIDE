#if ENABLE_GRPC
using Grpc.Net.Client;
using Gateway.AI.V1;

namespace GatewayIDE.App.Services.AI;

public sealed class AIClientService : IAsyncDisposable
{
    private readonly GrpcChannel _channel;
    private readonly AIService.AIServiceClient _client;

    public AIClientService(string endpoint)
    {
        _channel = GrpcChannel.ForAddress(endpoint);
        _client = new AIService.AIServiceClient(_channel);
    }

    public async Task<string> EchoAsync(string text, CancellationToken ct = default)
    {
        var reply = await _client.EchoAsync(new EchoRequest { Text = text }, cancellationToken: ct);
        return reply.Text;
    }

    public ValueTask DisposeAsync()
    {
        _channel.Dispose();
        return ValueTask.CompletedTask;
    }
}
#endif
