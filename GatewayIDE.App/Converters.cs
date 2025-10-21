// Converters.cs
using System;
using Avalonia.Data.Converters;
using System.Globalization;

namespace GatewayIDE.App
{
    public sealed class HalfConverter : IValueConverter
    {
        public object? Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
        {
            if (value is double d && !double.IsNaN(d) && !double.IsInfinity(d))
                return Math.Max(48, d * 0.5); // mind. 48px, sonst Hälfte
            return 200d;
        }

        public object? ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture)
            => throw new NotSupportedException();
    }
}
