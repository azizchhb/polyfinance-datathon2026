"""
AlphaForge Quantitative Engine - Piste A Calculations
Framework: Markowitz Portfolio Theory, Covariance, Risk Contributions, & Max Drawdown.
Author: Quantitative Finance Engine
"""

import numpy as np
import pandas as pd


class PisteACalculations:
    def __init__(self, prices_df: pd.DataFrame, weights: np.array, risk_free_rate: float = 0.035):
        """
        Initializes Piste A calculation engine.
        :param prices_df: DataFrame of historical asset prices (columns = assets, rows = dates)
        :param weights: 1D numpy array of portfolio weights (summing to 1.0)
        :param risk_free_rate: Annualized risk-free rate default (e.g., 3.5%)
        """
        self.prices_df = prices_df
        self.weights = np.array(weights, dtype=float)
        self.rf = risk_free_rate
        self.returns_df = None
        self.cov_matrix = None
        self.portfolio_volatility = 0.0

    def step_1_prices_to_returns(self, fx_rates: pd.Series = None) -> pd.DataFrame:
        """
        [Étape 1] Converts asset prices to returns, handles CAD conversion and calendar alignment.
        Formula: R_t = ln(P_t / P_{t-1})
        """
        converted_prices = self.prices_df.copy()
        if fx_rates is not None:
            # Convert foreign prices to CAD if FX rate series is provided
            for col in converted_prices.columns:
                if col in fx_rates:
                    converted_prices[col] = converted_prices[col] * fx_rates[col]

        # Calculate log returns with calendar alignment and drop NaN
        self.returns_df = np.log(converted_prices / converted_prices.shift(1)).dropna()
        return self.returns_df

    def step_2_markowitz_volatility(self) -> tuple:
        """
        [Étape 2] Computes annual covariance matrix and Markowitz portfolio volatility.
        Formula: Volatility (sigma_p) = sqrt(w^T * Cov * w) * sqrt(252)
        """
        if self.returns_df is None:
            raise ValueError("Run step_1_prices_to_returns first!")

        # Annualized covariance matrix (assuming 252 trading days)
        self.cov_matrix = self.returns_df.cov() * 252

        # Portfolio variance = w^T * Cov * w
        portfolio_variance = np.dot(self.weights.T, np.dot(self.cov_matrix, self.weights))
        self.portfolio_volatility = np.sqrt(portfolio_variance)

        return self.cov_matrix, self.portfolio_volatility

    def step_3_risk_contribution(self) -> pd.DataFrame:
        """
        [Étape 3] Calculates the risk contribution (RC) of each asset to total portfolio volatility.
        Formula: MRC_i = (Cov * w)_i / sigma_p
                 RC_i = w_i * MRC_i / sigma_p  (Percentage Risk Contribution)
        """
        if self.cov_matrix is None:
            self.step_2_markowitz_volatility()

        cov_dot_weights = np.dot(self.cov_matrix, self.weights)
        mrc = cov_dot_weights / self.portfolio_volatility  # Marginal Risk Contribution
        rc = self.weights * mrc  # Absolute Risk Contribution
        pct_rc = rc / self.portfolio_volatility  # Percentage Risk Contribution

        risk_contrib_df = pd.DataFrame(
            {
                "Weight": self.weights,
                "Marginal_Risk_Contrib": mrc,
                "Absolute_Risk_Contrib": rc,
                "Pct_Risk_Contrib": pct_rc,
            },
            index=self.returns_df.columns,
        )

        return risk_contrib_df

    def step_4_maximum_drawdown(self) -> dict:
        """
        [Étape 4] Computes historical maximum drawdown (MDD) of the weighted portfolio.
        Formula: Drawdown_t = (Peak_t - Value_t) / Peak_t ; MDD = max(Drawdown_t)
        """
        if self.returns_df is None:
            raise ValueError("Run step_1_prices_to_returns first!")

        # Calculate cumulative portfolio returns
        portfolio_daily_returns = np.dot(self.returns_df, self.weights)
        cumulative_wealth = np.cumprod(1 + portfolio_daily_returns)

        # Calculate running maximum peak
        running_max = np.maximum.accumulate(cumulative_wealth)

        # Calculate drawdowns
        drawdowns = (cumulative_wealth - running_max) / running_max
        max_drawdown = np.min(drawdowns)

        return {
            "max_drawdown": float(max_drawdown),
            "cumulative_wealth_series": cumulative_wealth,
            "drawdown_series": drawdowns,
        }

    def step_5_assemble_response(self, asset_classes: dict, sectors: dict) -> dict:
        """
        [Étape 5] Assembles final structured response containing weights, asset classes,
        sectors, and tracking uncovered symbols.
        """
        risk_contrib = self.step_3_risk_contribution()
        mdd_results = self.step_4_maximum_drawdown()

        summary = []
        for asset in self.returns_df.columns:
            summary.append(
                {
                    "symbol": asset,
                    "weight": float(risk_contrib.loc[asset, "Weight"]),
                    "asset_class": asset_classes.get(asset, "Unclassified"),
                    "sector": sectors.get(asset, "Uncovered / Other"),
                    "pct_risk_contribution": float(risk_contrib.loc[asset, "Pct_Risk_Contrib"]),
                }
            )

        return {
            "portfolio_volatility": float(self.portfolio_volatility),
            "maximum_drawdown": float(mdd_results["max_drawdown"]),
            "assets_breakdown": summary,
        }


# ==========================================
# Example Execution Block for Local Testing
# ==========================================
if __name__ == "__main__":
    # Mock price data for demonstration (3 assets over 5 days)
    np.random.seed(42)
    dates = pd.date_range(start="2026-01-01", periods=100, freq="B")
    mock_prices = pd.DataFrame(
        {
            "AAPL": np.cumprod(1 + np.random.normal(0.0005, 0.015, 100)) * 150,
            "MSFT": np.cumprod(1 + np.random.normal(0.0004, 0.012, 100)) * 300,
            "AGG": np.cumprod(1 + np.random.normal(0.0001, 0.004, 100)) * 100,
        },
        index=dates,
    )

    # Initialize weights summing to 1.0
    weights = [0.5, 0.3, 0.2]

    # Metadata mappings
    classes = {"AAPL": "Equity", "MSFT": "Equity", "AGG": "Fixed Income"}
    sectors = {"AAPL": "Technology", "MSFT": "Technology", "AGG": "Bonds"}

    engine = PisteACalculations(mock_prices, weights)
    returns = engine.step_1_prices_to_returns()
    cov, vol = engine.step_2_markowitz_volatility()
    risk_df = engine.step_3_risk_contribution()
    mdd = engine.step_4_maximum_drawdown()
    final_output = engine.step_5_assemble_response(classes, sectors)

    print("=== PISTE A CALCULATION RESULTS ===")
    print(f"Portfolio Annualized Volatility: {final_output['portfolio_volatility']:.4f}")
    print(f"Historical Maximum Drawdown: {final_output['maximum_drawdown']:.4f}\n")
    print("Risk Contribution Breakdown:")
    print(risk_df)
