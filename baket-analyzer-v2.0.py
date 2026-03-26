import datetime as dt
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from scipy import stats
from scipy.stats import binom, norm
import matplotlib.cm as cm
import matplotlib.ticker as mticker
from typing import List, Optional, Tuple
from matplotlib.dates import DateFormatter
import tkinter as tk
from tkinter import ttk, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import requests
from bs4 import BeautifulSoup

class ExtendedBasketAnalyzer:
    """
    Clase extendida para analizar baskets para notas estructuradas equity-linked.
    """
    
    def __init__(self, tickers: List[str], coupon_barrier: float = 0.0, capital_barrier: float = 0.5, 
                 duration_months: float = 24.0, annual_yield: float = 0.05, leveraged_put: float = 0.0, 
                 autocall_barrier: float = 1.0, months: int = 12, confidence: float = 0.95, 
                 M: int = 500000, seed: int = 42):
        self.tickers = tickers
        self.K = len(tickers)
        self.coupon_barrier = coupon_barrier
        self.capital_barrier = capital_barrier
        self.duration = duration_months / 12.0
        self.annual_yield = annual_yield
        self.leveraged_put = leveraged_put
        self.autocall_barrier = autocall_barrier
        self.months = months
        self.confidence = confidence
        self.M = M
        self.seed = seed
        
        self.freq = 4  # Quarterly coupons
        self.n = int(self.duration * self.freq)  # Number of periods
        self.dt = self.duration / self.n
        
        self.data: Optional[pd.DataFrame] = None
        self.normalized: Optional[pd.DataFrame] = None
        self.returns: Optional[pd.DataFrame] = None
        self.mu_vector: Optional[pd.Series] = None
        self.sigma_individual: Optional[np.ndarray] = None
        self.cov: Optional[np.ndarray] = None
        self.corr: Optional[pd.DataFrame] = None
        self.precio_port: Optional[pd.Series] = None
        self.vol_port: Optional[float] = None
        self.barrera_inf_worst: Optional[float] = None
        self.worst_St: Optional[np.ndarray] = None
        self.time_sim: Optional[np.ndarray] = None
        self.p_autocall: Optional[float] = None
        self.p_break: Optional[float] = None
        self.expected_coupon_proportion: Optional[float] = None
        self.expected_redemption: Optional[float] = None
        self.max_dd_average: Optional[float] = None
        self.pesos = np.ones(self.K) / self.K
        
    def fetch_data(self) -> None:
        end = dt.datetime.now()
        start = end - dt.timedelta(days=self.months * 30 + 10)
        self.data = yf.download(self.tickers, start=start, end=end, auto_adjust=True, progress=False)['Close']
        if self.data.empty or self.data.shape[1] < self.K:
            raise ValueError("No data for tickers.")
        if self.data.isna().any().any():
            self.data = self.data.dropna()
        if len(self.data) < self.months * 20 / 12:  # Approximate trading days
            raise ValueError("Not enough data for the horizon.")
        
        self.normalized = (self.data / self.data.iloc[0]) * 1.0
        self.normalized.columns = [col if not isinstance(col, tuple) else col[1] for col in self.normalized.columns]
        
        self.returns = self.normalized.pct_change().dropna()
        self.mu_vector = self.returns.mean() * 252
        self.cov = self.returns.cov() * 252
        self.corr = self.returns.corr()
        self.sigma_individual = np.sqrt(np.diag(self.cov))
        
        self.mu = np.mean(self.mu_vector)
        self.sigma = np.mean(self.sigma_individual)
        
    def compute_historical(self) -> None:
        if self.returns is None:
            raise ValueError("Run fetch_data first.")
        
        ret_port = (self.returns * self.pesos).sum(axis=1)
        self.precio_port = (1 + ret_port).cumprod() * 1.0
        self.vol_port = ret_port.std() * np.sqrt(252)
        
        worst_returns = self.returns.min(axis=1)
        media_worst = worst_returns.mean()
        std_worst = worst_returns.std()
        z_score = stats.norm.ppf(1 - (1 - self.confidence))
        self.barrera_inf_worst = 1.0 * (1 + media_worst - z_score * std_worst)
        
    def simulate_gbm(self) -> None:
        if self.mu_vector is None or self.cov is None:
            raise ValueError("Run fetch_data first.")
        
        np.random.seed(self.seed)
        S0 = 1.0
        chol = np.linalg.cholesky(self.cov)
        Z = np.random.normal(0, 1, size=(self.K, self.M, self.n))
        dW = np.einsum('ij,jkl->ikl', chol, Z)
        drift = (self.mu_vector.values[:, np.newaxis, np.newaxis] - 0.5 * self.sigma_individual[:, np.newaxis, np.newaxis]**2) * self.dt
        diffusion = np.sqrt(self.dt) * dW
        log_returns = drift + diffusion
        cum_log = np.cumsum(log_returns, axis=2)
        St = S0 * np.exp(cum_log)
        St = np.insert(St, 0, S0, axis=2)
        self.worst_St = np.min(St, axis=0)  # (M, n+1)
        self.time_sim = np.linspace(0, self.duration, self.n + 1)
        
    def calculate_probabilities(self) -> None:
        if self.worst_St is None:
            raise ValueError("Run simulate_gbm first.")
        
        coupon_per_period = self.annual_yield / self.freq
        L = self.leveraged_put
        autocall_counts = 0
        break_counts = 0
        total_coupons = np.zeros(self.M)
        redemptions = np.zeros(self.M)
        max_dds = np.zeros(self.M)
        
        for m in range(self.M):
            active = True
            coupons_paid = 0
            wo_path = self.worst_St[m, :]
            max_price = wo_path[0]
            max_dd = 0
            for i in range(1, self.n):
                wo = wo_path[i]
                if active:
                    if self.coupon_barrier == 0 or wo >= self.coupon_barrier:
                        coupons_paid += 1
                    if wo >= self.autocall_barrier:
                        autocall_counts += 1
                        active = False
            if active:
                wo = wo_path[self.n]
                if self.coupon_barrier == 0 or wo >= self.coupon_barrier:
                    coupons_paid += 1
                if wo >= self.capital_barrier:
                    redemption = 1.0
                else:
                    drop = 1.0 - wo
                    buffer = 1.0 - L
                    loss = max(0, drop - buffer)
                    redemption = 1.0 - loss
                redemptions[m] = redemption
                if wo < self.capital_barrier:
                    break_counts += 1
            else:
                redemptions[m] = 1.0
            total_coupons[m] = coupons_paid
            # Max drawdown
            current_dd = 0
            for p in wo_path:
                max_price = max(max_price, p)
                current_dd = (max_price - p) / max_price
                max_dd = max(max_dd, current_dd)
            max_dds[m] = max_dd
        self.p_autocall = autocall_counts / self.M
        self.p_break = break_counts / self.M
        if self.coupon_barrier > 0:
            self.expected_coupon_proportion = np.mean(total_coupons) / self.n
        else:
            self.expected_coupon_proportion = 1.0
        self.expected_redemption = np.mean(redemptions)
        self.max_dd_average = np.mean(max_dds)
        
    def set_historical_months(self, months: int) -> None:
        self.months = months
        self.fetch_data()
        self.compute_historical()
        
    def get_target_prices(self) -> Tuple[dict, dict, dict]:
        current = {}
        targets = {}
        probs = {}
        t = 1.0  # 1 year
        for tick in self.tickers:
            ticker = yf.Ticker(tick)
            info = ticker.info
            curr = info.get('previousClose', np.nan)
            trg = info.get('targetMeanPrice', np.nan)
            print(f"Debug yf for {tick}: previousClose = {curr}, targetMeanPrice = {trg}")
            if np.isnan(trg):
                curr, trg = self.scrape_yahoo_target(tick)
            current[tick] = curr
            targets[tick] = trg
            if np.isnan(curr) or np.isnan(trg) or tick not in self.mu_vector.index:
                probs[tick] = np.nan
                continue
            mu = self.mu_vector[tick]
            sigma = self.sigma_individual[self.tickers.index(tick)]
            drift = (mu - 0.5 * sigma**2) * t
            vol = sigma * np.sqrt(t) if sigma > 0 else 0.0001  # Avoid division by zero
            log_ratio = np.log(trg / curr)
            if trg >= curr:
                # P(S1 >= trg)
                d = (drift - log_ratio) / vol
                prob = norm.cdf(d)
            else:
                # P(S1 <= trg)
                d = (log_ratio - drift) / vol
                prob = norm.cdf(d)
            probs[tick] = prob
        return current, targets, probs
    
    def scrape_yahoo_target(self, tick: str) -> Tuple[float, float]:
        url = f"https://finance.yahoo.com/quote/{tick}"
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Failed to fetch page for {tick}: Status {response.status_code}")
            return np.nan, np.nan
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # Find Previous Close
        previous_close_span = soup.find('fin-streamer', {'data-field': 'regularMarketPreviousClose'})
        previous_close = float(previous_close_span['value']) if previous_close_span and 'value' in previous_close_span.attrs else np.nan
        
        # Find 1y Target Est
        target_est_span = soup.find('fin-streamer', {'data-field': 'targetMeanPrice'})
        target = float(target_est_span['value']) if target_est_span and 'value' in target_est_span.attrs else np.nan
        
        print(f"Scraped for {tick}: Previous Close = {previous_close}, 1y Target Est = {target}")  # Debug
        
        return previous_close, target
        
    def get_most_volatile_stable(self) -> Tuple[str, str]:
        if self.sigma_individual is None:
            raise ValueError("Run fetch_data first.")
        idx_max = np.argmax(self.sigma_individual)
        idx_min = np.argmin(self.sigma_individual)
        return self.tickers[idx_max], self.tickers[idx_min]
    
    def plot_historical(self) -> plt.Figure:
        fig, ax = plt.subplots(figsize=(8, 6))
        colors = cm.tab10(np.linspace(0, 1, self.K))
        for i, col in enumerate(self.normalized.columns):
            ax.plot(self.normalized.index, self.normalized[col], color=colors[i], alpha=0.7, label=col)
        ax.plot(self.precio_port.index, self.precio_port, color='black', linewidth=2, label='Portfolio')
        ax.axhline(y=self.barrera_inf_worst, color='darkred', linestyle='--', label=f'Hist Barrier ({self.barrera_inf_worst:.2f})')
        ax.set_title(f'Historical Performance over {self.months // 12} Years')
        ax.set_ylabel('Normalized Price')
        ax.xaxis.set_major_formatter(DateFormatter('%b-%y'))
        ax.legend()
        ax.grid(True)
        return fig
    
    def plot_scatter(self) -> plt.Figure:
        fig, ax = plt.subplots(figsize=(8, 6))
        colors = cm.tab10(np.linspace(0, 1, self.K))
        for i, ticker in enumerate(self.tickers):
            ax.scatter(self.mu_vector[ticker], self.sigma_individual[i], s=100, c=[colors[i]], label=ticker)
        ax.axhline(y=self.sigma, color='red', linestyle='--', label=f'Avg σ: {self.sigma:.2f}')
        ax.axvline(x=self.mu, color='blue', linestyle='--', label=f'Avg μ: {self.mu:.2f}')
        ax.set_xlabel('Annualized Drift (μ)')
        ax.set_ylabel('Annualized Volatility (σ)')
        ax.set_title('Scatter μ vs σ')
        ax.legend()
        ax.grid(True)
        return fig
    
    def plot_simulations(self) -> plt.Figure:
        fig, ax = plt.subplots(figsize=(8, 6))
        num_plots = min(self.M, 10)
        for m in range(num_plots):
            ax.plot(self.time_sim, self.worst_St[m, :], alpha=0.7)
        ax.axhline(y=self.capital_barrier, color='r', linestyle='--', label=f'Capital Barrier {self.capital_barrier:.2f}')
        ax.set_xlabel('Years')
        ax.set_ylabel('Worst-of Price')
        ax.set_title('GBM Simulations for WO')
        ax.grid(True)
        return fig
    
    def plot_upside_prob(self, current, targets, probs) -> plt.Figure:
        fig, ax = plt.subplots(figsize=(10, 6))
        tickers_plot = []
        target_percs = []
        prob_values = []
        colors = []
        for t in self.tickers:
            if np.isnan(probs.get(t, np.nan)):
                continue
            c = current.get(t, np.nan)
            trg = targets.get(t, np.nan)
            if np.isnan(c) or np.isnan(trg) or c == 0:
                continue
            target_perc = (trg / c) * 100
            prob = probs[t]
            tickers_plot.append(t)
            target_percs.append(target_perc)
            prob_values.append(prob)
            colors.append('green' if target_perc >= 100 else 'red')
        
        if not tickers_plot:
            ax.text(0.5, 0.5, 'No target data available', ha='center')
            return fig
        
        # Sort by target_perc
        sorted_idx = np.argsort(target_percs)
        tickers_plot = [tickers_plot[i] for i in sorted_idx]
        target_percs = [target_percs[i] for i in sorted_idx]
        prob_values = [prob_values[i] for i in sorted_idx]
        colors = [colors[i] for i in sorted_idx]
        
        for i, (ticker, target_perc, prob, color) in enumerate(zip(tickers_plot, target_percs, prob_values, colors)):
            if target_perc >= 100:
                width = target_perc - 100
                left = 100
                ha = 'left'
                text_x = target_perc + 0.5
            else:
                width = 100 - target_perc
                left = target_perc
                ha = 'right'
                text_x = target_perc - 0.5
            ax.barh(ticker, width, left=left, color=color, height=0.8)
            ax.text(text_x, i, f'{prob:.1%}', va='center', ha=ha, fontsize=10)
        
        ax.axvline(100, color='black', lw=1, linestyle='--')
        ax.set_xlabel('Target Price (%)')
        ax.set_title('1-Year Target Price from Issue (100%) with Achievement Probability')
        min_perc = min(50, min(target_percs) - 10) if target_percs else 50
        max_perc = max(150, max(target_percs) + 10) if target_percs else 150
        ax.set_xlim(min_perc, max_perc)
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, pos: f'{x:.0f}%'))
        ax.grid(True, alpha=0.3)
        return fig

class Dashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Structured Note Analysis Dashboard - Capital Driver Quantitative Tool")
        self.geometry("1200x800")
        
        # Input form
        frame = tk.Frame(self)
        frame.pack(pady=10)
        
        labels = ["Tickers (comma separated):", "Coupon Barrier (%):", "Capital Barrier (%):", 
                  "Duration (months):", "Annual Yield (%):", "Leveraged Put (%):", "Autocall Barrier (%):"]
        self.entries = {}
        for i, label in enumerate(labels):
            row = i // 3
            col = (i % 3) * 2
            tk.Label(frame, text=label).grid(row=row, column=col, sticky='e', padx=5, pady=5)
            entry = tk.Entry(frame)
            entry.grid(row=row, column=col+1, sticky='w', padx=5, pady=5)
            self.entries[label] = entry
        
        button_frame = tk.Frame(self)
        button_frame.pack(pady=5)
        tk.Button(button_frame, text="Run", command=self.run_analysis).pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="Clear", command=self.clear).pack(side=tk.LEFT)
        
        # Notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True)
        
        self.tabs = {}
        for title in ["Historical", "Simulations & Risk", "Sensitivity", "Upside/Downside"]:
            tab = tk.Frame(self.notebook)
            self.notebook.add(tab, text=title)
            self.tabs[title] = tab
        
        # For Historical tab
        historical_tab = self.tabs["Historical"]
        self.year_var = tk.StringVar(value="1")
        self.historical_combobox = ttk.Combobox(historical_tab, textvariable=self.year_var, values=["1", "3", "5", "10"])
        self.historical_combobox.pack()
        self.historical_update_button = tk.Button(historical_tab, text="Update Historical", command=self.update_historical)
        self.historical_update_button.pack()
        
        self.analyzer = None
        self.canvas = {}
        
    def run_analysis(self):
        try:
            tickers = [t.strip() for t in self.entries["Tickers (comma separated):"].get().split(',')]
            coupon_barrier = float(self.entries["Coupon Barrier (%):"].get() or 0) / 100
            capital_barrier = float(self.entries["Capital Barrier (%):"].get() or 50) / 100
            duration_months = float(self.entries["Duration (months):"].get() or 24)
            annual_yield = float(self.entries["Annual Yield (%):"].get() or 5) / 100
            leveraged_put = float(self.entries["Leveraged Put (%):"].get() or 0) / 100
            autocall_barrier = float(self.entries["Autocall Barrier (%):"].get() or 100) / 100
            
            self.analyzer = ExtendedBasketAnalyzer(tickers, coupon_barrier, capital_barrier, duration_months, annual_yield, 
                                                   leveraged_put, autocall_barrier)
            self.analyzer.fetch_data()
            self.analyzer.compute_historical()
            self.analyzer.simulate_gbm()
            self.analyzer.calculate_probabilities()
            
            self.update_historical()
            self.update_sim_risk()
            self.update_sensitivity()
            self.update_upside()
        except ValueError as e:
            messagebox.showerror("Error", str(e))
        
    def clear(self):
        for entry in self.entries.values():
            entry.delete(0, tk.END)
        for tab in self.tabs.values():
            for child in tab.winfo_children():
                child.destroy()
        # Re-create historical combobox and button
        historical_tab = self.tabs["Historical"]
        self.year_var = tk.StringVar(value="1")
        self.historical_combobox = ttk.Combobox(historical_tab, textvariable=self.year_var, values=["1", "3", "5", "10"])
        self.historical_combobox.pack()
        self.historical_update_button = tk.Button(historical_tab, text="Update Historical", command=self.update_historical)
        self.historical_update_button.pack()
        self.analyzer = None
        self.canvas = {}
        
    def update_historical(self):
        if self.analyzer is None:
            return
        historical_tab = self.tabs["Historical"]
        for child in historical_tab.winfo_children():
            if child not in [self.historical_combobox, self.historical_update_button]:
                child.destroy()
        year = int(self.year_var.get())
        try:
            self.analyzer.set_historical_months(year * 12)
            fig = self.analyzer.plot_historical()
            canvas = FigureCanvasTkAgg(fig, historical_tab)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            self.canvas["Historical"] = canvas
        except ValueError as e:
            tk.Label(historical_tab, text=str(e)).pack()
        
    def update_sim_risk(self):
        tab = self.tabs["Simulations & Risk"]
        for child in tab.winfo_children():
            child.destroy()
        text = tk.Text(tab, height=10)
        text.insert(tk.END, f"Prob Autocall: {self.analyzer.p_autocall:.2%}\n")
        text.insert(tk.END, f"Prob Break Capital at Term: {self.analyzer.p_break:.2%}\n")
        if self.analyzer.coupon_barrier > 0:
            text.insert(tk.END, f"Expected Coupon Proportion: {self.analyzer.expected_coupon_proportion:.2%}\n")
        text.insert(tk.END, f"Average Max Drawdown: {self.analyzer.max_dd_average:.2%}\n")
        text.insert(tk.END, f"Expected Redemption: {self.analyzer.expected_redemption:.2f}\n")
        # Stress test
        original_mu = self.analyzer.mu_vector.copy()
        original_sigma = self.analyzer.sigma_individual.copy()
        self.analyzer.mu_vector = original_mu - 0.05
        self.analyzer.sigma_individual = original_sigma * 1.5
        self.analyzer.simulate_gbm()
        self.analyzer.calculate_probabilities()
        text.insert(tk.END, "Under Stress\n")
        text.insert(tk.END, f"Prob Autocall: {self.analyzer.p_autocall:.2%}\n")
        text.insert(tk.END, f"Prob Break Capital at Term: {self.analyzer.p_break:.2%}\n")
        text.pack()
        # Restore
        self.analyzer.mu_vector = original_mu
        self.analyzer.sigma_individual = original_sigma
        self.analyzer.simulate_gbm()
        self.analyzer.calculate_probabilities()
        fig = self.analyzer.plot_simulations()
        canvas = FigureCanvasTkAgg(fig, tab)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas["Simulations & Risk"] = canvas
        
    def update_sensitivity(self):
        tab = self.tabs["Sensitivity"]
        for child in tab.winfo_children():
            child.destroy()
        most_vol, most_stable = self.analyzer.get_most_volatile_stable()
        text = tk.Text(tab, height=5)
        text.insert(tk.END, f"Most Volatile: {most_vol}\n")
        text.insert(tk.END, f"Most Stable: {most_stable}\n")
        text.pack()
        fig = self.analyzer.plot_scatter()
        canvas = FigureCanvasTkAgg(fig, tab)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas["Sensitivity"] = canvas
        
    def update_upside(self):
        tab = self.tabs["Upside/Downside"]
        for child in tab.winfo_children():
            child.destroy()
        current, targets, probs = self.analyzer.get_target_prices()
        fig = self.analyzer.plot_upside_prob(current, targets, probs)
        canvas = FigureCanvasTkAgg(fig, tab)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas["Upside/Downside"] = canvas

if __name__ == "__main__":
    app = Dashboard()
    app.mainloop()