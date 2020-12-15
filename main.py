https://www.quantconnect.com/forum/discussion/9597/the-in-amp-out-strategy-continued-from-quantopian/p3/comment-28146

"""
Based on 'In & Out' strategy by Peter Guenther 4 Oct 2020
expanded/inspired by Tentor Testivis, Dan Whitnable, Vladimir, and Thomas Chang.

"""
import numpy as np

class DualMomentumInOut(QCAlgorithm):

    def Initialize(self):

        self.SetStartDate(2008, 1, 1)
        # self.SetEndDate(2020, 11, 27)
        self.cap = 100000

        self.BND1 = self.AddEquity('TLT', Resolution.Minute).Symbol
        self.BND2 = self.AddEquity('TLH', Resolution.Minute).Symbol
        self.STK1 = self.AddEquity('QQQ', Resolution.Minute).Symbol
        self.STK2 = self.AddEquity('FDN', Resolution.Minute).Symbol

        self.MKT = self.AddEquity('SPY', Resolution.Daily).Symbol  
        self.XLI = self.AddEquity('XLI', Resolution.Daily).Symbol 
        self.XLU = self.AddEquity('XLU', Resolution.Daily).Symbol 
        self.SLV = self.AddEquity('SLV', Resolution.Daily).Symbol 
        self.GLD = self.AddEquity('GLD', Resolution.Daily).Symbol
        self.FXA = self.AddEquity('FXA', Resolution.Daily).Symbol
        self.FXF = self.AddEquity('FXF', Resolution.Daily).Symbol
        self.DBB = self.AddEquity('DBB', Resolution.Daily).Symbol  
        self.IGE = self.AddEquity('IGE', Resolution.Daily).Symbol
        self.SHY = self.AddEquity('SHY', Resolution.Daily).Symbol  
        self.UUP = self.AddEquity('UUP', Resolution.Daily).Symbol 

        self.FORPAIRS = [self.XLI, self.XLU, self.SLV, self.GLD, self.FXA, self.FXF]
        self.SIGNALS  = [self.XLI, self.DBB, self.IGE, self.SHY, self.UUP]
        self.pairlist = ['S_G', 'I_U', 'A_F']
        
        self.INI_WAIT_DAYS = 15
        self.mom = 126
        self.excl = 5
        
        self.BNDselect = self.BND1
        self.STKselect = self.STK1
        self.HLD_OUT = {self.BNDselect: 1}
        self.HLD_IN = {self.STKselect: 1}
        
        self.bull = 1 
        self.count = 0 
        self.outday = 0
        self.spy = []
        self.wait_days = self.INI_WAIT_DAYS
        self.SetWarmUp(timedelta(126))

        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen('SPY', 1),
            self.calculate_signal)

        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen('SPY', 120),
            self.rebalance_when_out_of_the_market)

        self.Schedule.On(self.DateRules.WeekEnd(), self.TimeRules.AfterMarketOpen('SPY', 121),
            self.rebalance_when_in_the_market)
            
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.BeforeMarketClose('SPY', 0), 
            self.record_vars)  
            
            
        symbols = self.SIGNALS + [self.MKT] + self.FORPAIRS
        for symbol in symbols:
            self.consolidator = TradeBarConsolidator(timedelta(days = 1))
            self.consolidator.DataConsolidated += self.consolidation_handler
            self.SubscriptionManager.AddConsolidator(symbol, self.consolidator)
            
        self.lookback = 252
        self.history = self.History(symbols, self.lookback, Resolution.Daily)
        if self.history.empty or 'close' not in self.history.columns:
            return
        self.history = self.history['close'].unstack(level=0).dropna()
        self.update_history_shift() 
        
        
    def consolidation_handler(self, sender, consolidated):
        self.history.loc[consolidated.EndTime, consolidated.Symbol] = consolidated.Close
        self.history = self.history.iloc[-self.lookback:]
        self.update_history_shift()
        
        
    def update_history_shift(self):
        self.history_shift_mean = self.history.shift(55).rolling(11).mean()    
            
   
    def Returns(self, symbol, period, excl):
        prices = self.History(symbol, TimeSpan.FromDays(period + excl), Resolution.Daily).close
        return prices[-excl] / prices[0]
        
        
    def calculate_signal(self):
        mom = (self.history / self.history_shift_mean - 1)

        mom[self.UUP] = mom[self.UUP] * (-1)
        mom['S_G'] = mom[self.SLV] - mom[self.GLD]
        mom['I_U'] = mom[self.XLI] - mom[self.XLU]
        mom['A_F'] = mom[self.FXA] - mom[self.FXF]   

        pctl = np.nanpercentile(mom, 1, axis=0)
        extreme = mom.iloc[-1] < pctl

        self.wait_days = int(
            max(0.50 * self.wait_days,
                self.INI_WAIT_DAYS * max(1,
                                         np.where((mom[self.GLD].iloc[-1]>0) & (mom[self.SLV].iloc[-1]<0) & (mom[self.SLV].iloc[-2]>0), self.INI_WAIT_DAYS, 1),
                                         np.where((mom[self.XLU].iloc[-1]>0) & (mom[self.XLI].iloc[-1]<0) & (mom[self.XLI].iloc[-2]>0), self.INI_WAIT_DAYS, 1),
                                         np.where((mom[self.FXF].iloc[-1]>0) & (mom[self.FXA].iloc[-1]<0) & (mom[self.FXA].iloc[-2]>0), self.INI_WAIT_DAYS, 1)
                                         ))
        )
        adjwaitdays = min(60, self.wait_days)

        # self.Debug('{}'.format(self.wait_days))

        if (extreme[self.SIGNALS + self.pairlist]).any():
            self.bull = False
            self.outday = self.count
            
        if self.count >= self.outday + adjwaitdays:
            self.bull = True
            
        self.count += 1

        self.Plot("In Out", "in_market", int(self.bull))
        self.Plot("In Out", "num_out_signals", extreme[self.SIGNALS + self.pairlist].sum())
        self.Plot("Wait Days", "waitdays", adjwaitdays)

        if self.Returns(self.BND1, self.mom, self.excl) < self.Returns(self.BND2, self.mom, self.excl):
            self.BNDselect = self.BND2
            
        elif self.Returns(self.BND1, self.mom, self.excl) > self.Returns(self.BND2, self.mom, self.excl):
            self.BNDselect = self.BND1
            
        if self.Returns(self.STK1, self.mom, self.excl) < self.Returns(self.STK2, self.mom, self.excl):
            self.STKselect =  self.STK2
            
        elif self.Returns(self.STK1, self.mom, self.excl) > self.Returns(self.STK2, self.mom, self.excl):
            self.STKselect =  self.STK1
            
        self.HLD_IN = {self.STKselect: 1}
        self.HLD_OUT = {self.BNDselect: 1}
            

    def rebalance_when_out_of_the_market(self):
        if not self.bull:
            self.trade({**dict.fromkeys(self.HLD_IN, 0), **self.HLD_OUT})
            

    def rebalance_when_in_the_market(self):
        if self.bull:
            self.trade({**self.HLD_IN, **dict.fromkeys(self.HLD_OUT, 0)})
            self.Log(f"TotalPortfolioValue: {self.Portfolio.TotalPortfolioValue}, TotalMarginUsed: {self.Portfolio.TotalMarginUsed}, MarginRemaining: {self.Portfolio.MarginRemaining}, Cash:  {self.Portfolio.Cash}")
            for key in sorted(self.Portfolio.keys()):
                if self.Portfolio[key].Quantity > 0.0:
                    self.Log(f"Symbol/Qty: {key} / {self.Portfolio[key].Quantity}, Avg: {self.Portfolio[key].AveragePrice}, Curr: { self.Portfolio[key].Price}, Profit($): {self.Portfolio[key].UnrealizedProfit}")


    def trade(self, weight_by_sec):
        if self.Portfolio.Invested:
            for symbol in self.Portfolio.Keys:
                if symbol not in weight_by_sec:
                    self.Liquidate(symbol)
            
        buys = []
        for sec, weight in weight_by_sec.items():
            if not self.CurrentSlice.ContainsKey(sec) or self.CurrentSlice[sec] is None:
                continue
            
            cond1 = weight == 0 and self.Portfolio[sec].IsLong
            cond2 = weight > 0 and not self.Portfolio[sec].Invested
            if cond1 or cond2:
                quantity = self.CalculateOrderQuantity(sec, weight)
                if quantity > 0:
                    buys.append((sec, quantity))
                elif quantity < 0:
                    self.Order(sec, quantity)
        for sec, quantity in buys:
            self.Order(sec, quantity)
            
                    
    def record_vars(self):                
                
        hist = self.History([self.MKT], 2, Resolution.Daily)['close'].unstack(level= 0).dropna() 
        self.spy.append(hist[self.MKT].iloc[-1])
        spy_perf = self.spy[-1] / self.spy[0] * self.cap
        self.Plot("Strategy Equity", "SPY", spy_perf)
        
        account_leverage = self.Portfolio.TotalHoldingsValue / self.Portfolio.TotalPortfolioValue
        self.Plot('Holdings', 'leverage', round(account_leverage, 1))
