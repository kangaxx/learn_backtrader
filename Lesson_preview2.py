# 本例子用于展示通过tushare接口获取螺纹钢期货主力期货指数历史数据，并用Backtrader进行简单的回测。回测的策略是基于5日均线和20日均线的交叉策略。
import tushare as ts
import backtrader as bt
import pandas as pd
import json
import datetime
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei']  # 用来正常显示中文标签
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

# 加载tushare token
def load_tushare_token(token_file='Data/tushare_token.json'):
    try:
        with open(token_file, 'r', encoding='utf-8') as f:
            token_data = json.load(f)
            return token_data.get('token', '')
    except Exception as e:
        print(f"加载token文件失败: {e}")
        return ''

# 设置tushare token
token = load_tushare_token()
if token:
    ts.set_token(token)
    pro = ts.pro_api()
else:
    print("请在Data/tushare_token.json文件中设置有效的tushare token")
    exit()

# 从tushare获取螺纹钢期货主力期货指数数据
def get_rb_index_data(start_date='20200101', end_date=None):
    if end_date is None:
        end_date = datetime.datetime.now().strftime('%Y%m%d')
    
    # 螺纹钢期货主力期货指数的代码为RB.SHF
    df = pro.fut_daily(
        ts_code='RB.SHF',
        start_date=start_date,
        end_date=end_date
    )
    
    # 数据处理
    if df.empty:
        print("未能获取到螺纹钢期货主力期货指数数据")
        return None
    
    # 重命名列以便Backtrader使用
    df = df.rename(columns={
        'trade_date': 'date',
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'vol': 'volume'
    })
    
    # 将日期列转换为datetime格式
    df['date'] = pd.to_datetime(df['date'])
    
    # 按照日期排序
    df = df.sort_values('date')
    
    # 设置索引
    df.set_index('date', inplace=True)
    
    return df

# 定义策略类
class SmaCrossStrategy(bt.Strategy):
    params = (
        ('sma1', 5),    # 短期均线周期
        ('sma2', 20),   # 长期均线周期
    )
    
    def __init__(self):
        # 初始化日志
        self.log = self._log
        
        # 跟踪订单
        self.order = None
        
        # 跟踪持仓入场日期（用于判断是否为当日平仓）
        self.trade_entry_date = None
        
        # 创建两个移动平均线指标
        self.sma1 = bt.indicators.SimpleMovingAverage(
            self.datas[0].close, period=self.params.sma1
        )
        self.sma2 = bt.indicators.SimpleMovingAverage(
            self.datas[0].close, period=self.params.sma2
        )
        
        # 交叉信号
        self.crossover = bt.indicators.CrossOver(self.sma1, self.sma2)
    
    def _log(self, txt, dt=None):
        """记录策略日志"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')
    
    def notify_order(self, order):
        """订单通知"""
        if order.status in [order.Submitted, order.Accepted]:
            # 订单已经提交或接受，不需要处理
            return
        
        # 检查订单是否已完成
        if order.status in [order.Completed]:
            current_date = self.datas[0].datetime.date(0)
            
            if order.isbuy():  # 买入
                # 记录买入日期，用于判断是否为当日平仓
                self.trade_entry_date = current_date
                self.log(f'买入: 价格={order.executed.price:.2f}, 成本={order.executed.value:.2f}, 佣金={order.executed.comm:.2f}')
            elif order.issell():  # 卖出
                # 检查是否为当日平仓
                is_same_day_close = self.trade_entry_date == current_date
                self.log(f'卖出: 价格={order.executed.price:.2f}, 收入={order.executed.value:.2f}, 佣金={order.executed.comm:.2f}, 当日平仓={is_same_day_close}')
                # 如果不是当日平仓，重新计算佣金为0
                if not is_same_day_close:
                    order.executed.comm = 0.0
            
            # 记录订单完成的时间
            self.bar_executed = len(self)
        
        # 如果订单被取消、拒绝或保证金不足
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单被取消/拒绝/保证金不足')
        
        # 重置订单
        self.order = None
    
    def notify_trade(self, trade):
        """交易通知"""
        if not trade.isclosed:
            return
        
        # 检查是否为非当日平仓，如果是则调整佣金为0
        is_same_day_trade = trade.open_datetime.date() == trade.close_datetime.date()
        
        # 如果不是当日交易，重新计算佣金
        if not is_same_day_trade:
            # 只保留买入佣金，卖出佣金设为0
            original_commission = trade.commission
            adjusted_commission = 6.2  # 只保留买入佣金
            trade.commission = adjusted_commission
            
            # 重新计算净利润
            adjusted_pnlcomm = trade.pnl - adjusted_commission
            self.log(f'交易利润, 毛利润={trade.pnl:.2f}, 调整后佣金={adjusted_commission:.2f}, 调整后净利润={adjusted_pnlcomm:.2f} (非当日平仓)')
        else:
            self.log(f'交易利润, 毛利润={trade.pnl:.2f}, 净利润={trade.pnlcomm:.2f} (当日平仓)')
    
    def next(self):
        """策略核心逻辑"""
        # 如果有未完成的订单，不执行新的交易
        if self.order:
            return
        
        # 检查当前是否持仓
        if not self.position:
            # 没有持仓，检查是否有买入信号（短期均线上穿长期均线）
            if self.crossover > 0:
                self.log(f'买入信号: SMA{self.params.sma1}({self.sma1[0]:.2f}) 上穿 SMA{self.params.sma2}({self.sma2[0]:.2f})')
                # 买入
                self.order = self.buy()
        else:
            # 有持仓，检查是否有卖出信号（短期均线下穿长期均线）
            if self.crossover < 0:
                self.log(f'卖出信号: SMA{self.params.sma1}({self.sma1[0]:.2f}) 下穿 SMA{self.params.sma2}({self.sma2[0]:.2f})')
                # 卖出
                self.order = self.sell()

# 主函数
def main():
    # 获取数据
    print("正在获取螺纹钢期货主连数据...")
    df = get_rb_index_data(start_date='20200101')
    
    if df is None or df.empty:
        print("没有可用数据，无法进行回测")
        return
    
    print(f"获取到 {len(df)} 条数据记录")
    print("数据样例:")
    print(df.head())
    
    # 创建Backtrader数据馈送
    data = bt.feeds.PandasData(dataname=df)
    
    # 创建cerebro引擎
    cerebro = bt.Cerebro()
    
    # 添加数据
    cerebro.adddata(data)
    
    # 添加策略
    cerebro.addstrategy(SmaCrossStrategy)
    
    # 设置初始资金
    cerebro.broker.setcash(100000.0)
    
    # 设置自定义佣金：每手买入6.2元，当日平仓6.2元，非当日平仓免费
    class CommInfoFutures(bt.CommInfoBase):
        params = (
            ('stocklike', False),  # 期货模式
            ('commtype', bt.CommInfoBase.COMM_FIXED),  # 固定佣金
            ('commission', 6.2),  # 基础佣金（买入和当日平仓）
            ('mult', 1),  # 合约乘数
            ('margin', 0),  # 保证金率
        )
        
        def _getcommission(self, size, price, pseudoexec):
            # 买入订单总是收费6.2元/手
            if size > 0:
                return 6.2  # 买入收费
            # 卖出订单先按6.2元/手收费，后续在notify_order中会根据是否为当日平仓调整
            elif size < 0:
                return 6.2  # 卖出暂时收费，后续会在策略中调整
    
    # 创建佣金对象并设置到broker
    comminfo = CommInfoFutures()
    cerebro.broker.addcommissioninfo(comminfo)
    
    # 添加性能分析指标
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    
    # 打印初始资金
    print(f'初始资金: {cerebro.broker.getvalue():.2f}')
    
    # 运行回测
    print("正在运行回测...")
    results = cerebro.run()
    strategy = results[0]
    
    # 打印最终资金
    print(f'最终资金: {cerebro.broker.getvalue():.2f}')
    
    # 打印性能指标
    print("\n性能指标:")
    returns = strategy.analyzers.returns.get_analysis()
    print(f"总回报率: {returns['rtot']*100:.2f}%")
    print(f"年化回报率: {returns['rnorm100']:.2f}%")
    
    try:
        sharpe = strategy.analyzers.sharpe.get_analysis()
        print(f"夏普比率: {sharpe['sharperatio']:.2f}")
    except:
        print("无法计算夏普比率")
    
    drawdown = strategy.analyzers.drawdown.get_analysis()
    print(f"最大回撤: {drawdown['max']['drawdown']:.2f}%")
    print(f"最大回撤持续时间: {drawdown['max']['len']} 天")
    
    trades = strategy.analyzers.trades.get_analysis()
    if 'total' in trades and 'closed' in trades['total']:
        print(f"交易次数: {trades['total']['closed']}")
        if 'won' in trades and 'total' in trades['won']:
            win_rate = trades['won']['total'] / trades['total']['closed'] * 100 if trades['total']['closed'] > 0 else 0
            print(f"胜率: {win_rate:.2f}%")
    
    # 绘制回测结果
    print("\n绘制回测结果...")
    cerebro.plot(style='candlestick')

if __name__ == '__main__':
    main()