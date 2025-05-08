import os
import logging
import pandas as pd
import matplotlib.pyplot as plt
import datetime

logger = logging.getLogger("power_monitor")

class ReportGenerator:
    """Generates reports and visualizations from power monitoring data."""
    
    def __init__(self, output_dir):
        """Initialize the report generator."""
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_power_report(self, rack_name, data_df, start_time, end_time):
        """Generate a comprehensive report of power usage."""
        try:
            if data_df.empty:
                logger.warning(f"No data available for rack {rack_name}")
                return None
            
            # Filter out error readings and convert to numeric if needed
            if not pd.api.types.is_numeric_dtype(data_df['PowerWatts']):
                data_df = data_df[data_df['PowerWatts'] != 'ERROR']
                data_df['PowerWatts'] = pd.to_numeric(data_df['PowerWatts'], errors='coerce')
            
            # Drop missing values
            data_df = data_df.dropna(subset=['PowerWatts'])
            
            if data_df.empty:
                logger.warning(f"No valid power readings for rack {rack_name}")
                return None
            
            # Calculate statistics
            power_values = data_df['PowerWatts']
            avg_power = power_values.mean()
            min_power = power_values.min()
            max_power = power_values.max()
            std_dev = power_values.std()
            
            # Calculate energy consumption (watt-hours)
            total_energy = 0
            if len(data_df) > 1:
                data_df = data_df.sort_values('Timestamp')
                for i in range(1, len(data_df)):
                    time_diff = (pd.to_datetime(data_df['Timestamp'].iloc[i]) - 
                                pd.to_datetime(data_df['Timestamp'].iloc[i-1])).total_seconds() / 3600  # hours
                    avg_pwr = (data_df['PowerWatts'].iloc[i] + data_df['PowerWatts'].iloc[i-1]) / 2
                    total_energy += avg_pwr * time_diff
            
            # Generate timestamp for file naming
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            
            # Generate the report file
            report_path = os.path.join(self.output_dir, f"PowerReport-{rack_name}-{timestamp}.txt")
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(f"Power Monitoring Report for Rack: {rack_name}\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Monitoring Period: {start_time.strftime('%Y-%m-%d %H:%M:%S')} to {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                
                duration = (end_time - start_time).total_seconds() / 3600
                f.write(f"Duration: {duration:.2f} hours\n")
                f.write(f"Total Readings: {len(data_df)}\n\n")
                
                f.write("Power Statistics:\n")
                f.write(f"  Average Power: {avg_power:.2f} W\n")
                f.write(f"  Minimum Power: {min_power:.2f} W\n")
                f.write(f"  Maximum Power: {max_power:.2f} W\n")
                f.write(f"  Standard Deviation: {std_dev:.2f} W\n\n")
                
                f.write("Energy Consumption:\n")
                f.write(f"  Total Energy: {total_energy:.2f} Watt-hours ({total_energy/1000:.4f} kWh)\n\n")
                
                # Add time-based analysis
                if len(data_df) > 1:
                    data_df['Hour'] = pd.to_datetime(data_df['Timestamp']).dt.hour
                    hourly_avg = data_df.groupby('Hour')['PowerWatts'].mean()
                    
                    f.write("Hourly Power Usage:\n")
                    for hour, avg in hourly_avg.items():
                        f.write(f"  {hour:02d}:00 - {hour:02d}:59: {avg:.2f} W\n")
                    
                    # Identify peak times
                    peak_hour = hourly_avg.idxmax()
                    min_hour = hourly_avg.idxmin()
                    
                    f.write(f"\nPeak usage hour: {peak_hour:02d}:00 - {peak_hour:02d}:59 ({hourly_avg[peak_hour]:.2f} W)\n")
                    f.write(f"Minimum usage hour: {min_hour:02d}:00 - {min_hour:02d}:59 ({hourly_avg[min_hour]:.2f} W)\n")
            
            logger.info(f"Generated power report: {report_path}")
            
            # Create chart
            chart_path = self.generate_power_chart(rack_name, data_df, timestamp)
            
            return {
                'report_path': report_path,
                'chart_path': chart_path,
                'statistics': {
                    'avg_power': avg_power,
                    'min_power': min_power,
                    'max_power': max_power,
                    'std_dev': std_dev,
                    'total_energy': total_energy,
                    'duration': duration,
                    'readings': len(data_df)
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating report for rack {rack_name}: {e}")
            return None
    
    def generate_power_chart(self, rack_name, data_df, timestamp=None):
        """Generate a chart of power usage over time."""
        try:
            if data_df.empty:
                logger.warning(f"No data available for rack {rack_name}")
                return None
                
            if timestamp is None:
                timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            
            # Create figure
            plt.figure(figsize=(10, 6))
            
            # Plot power usage
            plt.plot(pd.to_datetime(data_df['Timestamp']), data_df['PowerWatts'], 
                    'b-', linewidth=2, marker='o', markersize=4)
            
            # Calculate statistics for reference lines
            avg_power = data_df['PowerWatts'].mean()
            min_power = data_df['PowerWatts'].min()
            max_power = data_df['PowerWatts'].max()
            
            # Add reference lines
            plt.axhline(y=avg_power, color='r', linestyle='-', label=f'Avg: {avg_power:.2f}W')
            plt.axhline(y=min_power, color='g', linestyle='--', label=f'Min: {min_power:.2f}W')
            plt.axhline(y=max_power, color='orange', linestyle='--', label=f'Max: {max_power:.2f}W')
            
            # Labels and title
            plt.title(f"Power Usage for {rack_name}")
            plt.xlabel("Time")
            plt.ylabel("Power (Watts)")
            plt.grid(True)
            plt.legend()
            
            # Format x-axis
            plt.gcf().autofmt_xdate()
            
            # Save chart
            chart_path = os.path.join(self.output_dir, f"PowerChart-{rack_name}-{timestamp}.png")
            plt.tight_layout()
            plt.savefig(chart_path)
            plt.close()
            
            logger.info(f"Generated power chart: {chart_path}")
            return chart_path
            
        except Exception as e:
            logger.error(f"Error generating chart for rack {rack_name}: {e}")
            return None
    
    def generate_comparison_chart(self, rack_data_dict, start_time=None, end_time=None):
        """Generate a comparison chart for multiple racks."""
        try:
            if not rack_data_dict:
                logger.warning("No rack data provided for comparison")
                return None
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            
            # Create figure
            plt.figure(figsize=(12, 8))
            
            # Plot each rack's data
            for rack_name, data_df in rack_data_dict.items():
                if data_df.empty:
                    continue
                    
                # Filter by time range if specified
                if start_time and end_time:
                    mask = ((pd.to_datetime(data_df['Timestamp']) >= start_time) & 
                           (pd.to_datetime(data_df['Timestamp']) <= end_time))
                    filtered_df = data_df[mask]
                else:
                    filtered_df = data_df
                
                if not filtered_df.empty:
                    plt.plot(pd.to_datetime(filtered_df['Timestamp']), 
                            filtered_df['PowerWatts'], 
                            marker='o', markersize=3, label=rack_name)
            
            # Labels and title
            plt.title("Rack Power Comparison")
            plt.xlabel("Time")
            plt.ylabel("Power (Watts)")
            plt.grid(True)
            plt.legend()
            
            # Format x-axis
            plt.gcf().autofmt_xdate()
            
            # Save chart
            chart_path = os.path.join(self.output_dir, f"PowerComparison-{timestamp}.png")
            plt.tight_layout()
            plt.savefig(chart_path)
            plt.close()
            
            logger.info(f"Generated comparison chart: {chart_path}")
            return chart_path
            
        except Exception as e:
            logger.error(f"Error generating comparison chart: {e}")
            return None