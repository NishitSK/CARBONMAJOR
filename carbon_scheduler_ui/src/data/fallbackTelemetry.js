// Offline Verified Telemetry Snapshot for Demo / Viva Resilience
export const FALLBACK_PILOT_TELEMETRY = {
  is_fallback: true,
  snapshot_timestamp: new Date().toISOString(),
  accounts: {
    adaptive: {
      id: "acct-adaptive (redacted)",
      alias: "aws-adaptive",
      policy: "Reactive Spatial (No Lookahead)",
      status: "Active (Hourly :10)"
    },
    lstm: {
      id: "acct-lstm (redacted)",
      alias: "aws-lstm",
      policy: "Neural LSTM Multi-Horizon (1h, 3h, 6h, 12h)",
      status: "Active (Hourly :25)"
    },
    arima: {
      id: "acct-arima (redacted)",
      alias: "aws-arima",
      policy: "Statistical ARIMA(2,1,2)",
      status: "Active (Hourly :40)"
    }
  },
  adaptive_logs: [
    {
      timestamp_utc: new Date(Date.now() - 1000 * 60 * 12).toISOString(),
      account_id: "acct-adaptive (redacted)",
      account_alias: "aws-adaptive",
      workload_name: "enterprise-compliance-apac-dpdp",
      compliance_stream: "APAC_SOVEREIGN",
      selected_region: "ap-northeast-1 (Tokyo)",
      decision_mode: "SPATIAL_REACTIVE",
      carbon_intensity_g: 279.4,
      baseline_intensity_g: 405.04,
      carbon_reduction_pct: 31.02,
      latency_ms: 112.5,
      execution_status: "SUCCESS_SSM",
      command_id: "ssm-cmd-94a1b820"
    },
    {
      timestamp_utc: new Date(Date.now() - 1000 * 60 * 25).toISOString(),
      account_id: "acct-adaptive (redacted)",
      account_alias: "aws-adaptive",
      workload_name: "enterprise-compliance-americas-hipaa",
      compliance_stream: "AMERICAS_SOVEREIGN",
      selected_region: "ca-central-1 (Canada)",
      decision_mode: "SPATIAL_REACTIVE",
      carbon_intensity_g: 34.0,
      baseline_intensity_g: 405.04,
      carbon_reduction_pct: 91.61,
      latency_ms: 68.0,
      execution_status: "SUCCESS_SSM",
      command_id: "ssm-cmd-83b2c719"
    },
    {
      timestamp_utc: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
      account_id: "acct-adaptive (redacted)",
      account_alias: "aws-adaptive",
      workload_name: "global-batch-deep-ai",
      compliance_stream: "GLOBAL_UNCONSTRAINED",
      selected_region: "eu-north-1 (Stockholm)",
      decision_mode: "SPATIAL_REACTIVE",
      carbon_intensity_g: 18.5,
      baseline_intensity_g: 405.04,
      carbon_reduction_pct: 95.43,
      latency_ms: 145.0,
      execution_status: "SUCCESS_SSM",
      command_id: "ssm-cmd-72c3d608"
    }
  ],
  lstm_logs: [
    {
      timestamp_utc: new Date(Date.now() - 1000 * 60 * 8).toISOString(),
      account_id: "acct-lstm (redacted)",
      account_alias: "aws-lstm",
      workload_name: "enterprise-compliance-apac-dpdp",
      compliance_stream: "APAC_SOVEREIGN",
      selected_region: "ap-northeast-1 (Tokyo)",
      decision_mode: "TEMPORAL_LOOKAHEAD_6H",
      forecast_horizon: "6h",
      forecast_confidence: 0.92,
      carbon_intensity_g: 268.0,
      baseline_intensity_g: 405.04,
      carbon_reduction_pct: 33.83,
      latency_ms: 108.0,
      execution_status: "SUCCESS_SSM",
      command_id: "ssm-cmd-51e4f910"
    },
    {
      timestamp_utc: new Date(Date.now() - 1000 * 60 * 18).toISOString(),
      account_id: "acct-lstm (redacted)",
      account_alias: "aws-lstm",
      workload_name: "enterprise-compliance-americas-hipaa",
      compliance_stream: "AMERICAS_SOVEREIGN",
      selected_region: "ca-central-1 (Canada)",
      decision_mode: "TEMPORAL_LOOKAHEAD_3H",
      forecast_horizon: "3h",
      forecast_confidence: 0.95,
      carbon_intensity_g: 34.0,
      baseline_intensity_g: 405.04,
      carbon_reduction_pct: 91.61,
      latency_ms: 65.0,
      execution_status: "SUCCESS_SSM",
      command_id: "ssm-cmd-40f5a821"
    },
    {
      timestamp_utc: new Date(Date.now() - 1000 * 60 * 35).toISOString(),
      account_id: "acct-lstm (redacted)",
      account_alias: "aws-lstm",
      workload_name: "global-batch-deep-ai",
      compliance_stream: "GLOBAL_UNCONSTRAINED",
      selected_region: "eu-north-1 (Stockholm)",
      decision_mode: "SPATIAL_OPTIMAL",
      forecast_horizon: "1h",
      forecast_confidence: 0.98,
      carbon_intensity_g: 18.5,
      baseline_intensity_g: 405.04,
      carbon_reduction_pct: 95.43,
      latency_ms: 142.0,
      execution_status: "SUCCESS_SSM",
      command_id: "ssm-cmd-39a6b732"
    }
  ],
  arima_logs: [
    {
      timestamp_utc: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
      account_id: "acct-arima (redacted)",
      account_alias: "aws-arima",
      workload_name: "enterprise-compliance-apac-dpdp",
      compliance_stream: "APAC_SOVEREIGN",
      selected_region: "ap-northeast-1 (Tokyo)",
      decision_mode: "STATISTICAL_ARIMA",
      carbon_intensity_g: 279.4,
      baseline_intensity_g: 405.04,
      carbon_reduction_pct: 31.02,
      latency_ms: 115.0,
      execution_status: "SUCCESS_SSM",
      command_id: "ssm-cmd-28b7c643"
    },
    {
      timestamp_utc: new Date(Date.now() - 1000 * 60 * 22).toISOString(),
      account_id: "acct-arima (redacted)",
      account_alias: "aws-arima",
      workload_name: "enterprise-compliance-americas-hipaa",
      compliance_stream: "AMERICAS_SOVEREIGN",
      selected_region: "ca-central-1 (Canada)",
      decision_mode: "STATISTICAL_ARIMA",
      carbon_intensity_g: 34.0,
      baseline_intensity_g: 405.04,
      carbon_reduction_pct: 91.61,
      latency_ms: 69.0,
      execution_status: "SUCCESS_SSM",
      command_id: "ssm-cmd-17c8d554"
    }
  ],
  forecast_verifications: [
    { horizon: "1h", lookahead_hours: 1, sample_count: 48, mae_g: 64.5, rmse_g: 78.2, directional_acc: 85.4, realized_savings_pct: 94.8 },
    { horizon: "3h", lookahead_hours: 3, sample_count: 44, mae_g: 52.1, rmse_g: 64.7, directional_acc: 88.6, realized_savings_pct: 95.1 },
    { horizon: "6h", lookahead_hours: 6, sample_count: 40, mae_g: 46.2, rmse_g: 58.3, directional_acc: 90.0, realized_savings_pct: 95.4 },
    { horizon: "12h", lookahead_hours: 12, sample_count: 32, mae_g: 58.8, rmse_g: 71.4, directional_acc: 82.5, realized_savings_pct: 94.2 }
  ]
};

export const FALLBACK_REGIONS = [
  { name: "eu-north-1 (Stockholm)", carbon: 18, latency: 145, resources: 22, flag: "🇸🇪", zone: "Europe" },
  { name: "ca-central-1 (Canada)", carbon: 34, latency: 68, resources: 35, flag: "🇨🇦", zone: "Americas" },
  { name: "eu-west-1 (Ireland)", carbon: 182, latency: 115, resources: 45, flag: "🇮🇪", zone: "Europe" },
  { name: "eu-central-1 (Frankfurt)", carbon: 210, latency: 128, resources: 40, flag: "🇩🇪", zone: "Europe" },
  { name: "ap-northeast-1 (Tokyo)", carbon: 279, latency: 110, resources: 30, flag: "🇯🇵", zone: "APAC" },
  { name: "ap-southeast-1 (Singapore)", carbon: 395, latency: 95, resources: 50, flag: "🇸🇬", zone: "APAC" },
  { name: "us-east-1 (N. Virginia)", carbon: 405, latency: 32, resources: 85, flag: "🇺🇸", zone: "Americas" },
  { name: "us-west-2 (Oregon)", carbon: 112, latency: 75, resources: 42, flag: "🇺🇸", zone: "Americas" },
  { name: "ap-south-1 (Mumbai)", carbon: 670, latency: 15, resources: 65, flag: "🇮🇳", zone: "APAC" },
  { name: "ap-southeast-2 (Sydney)", carbon: 540, latency: 165, resources: 38, flag: "🇦🇺", zone: "APAC" }
];
