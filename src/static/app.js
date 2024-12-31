const { createApp } = Vue

createApp({
    data() {
        return {
            summary: {
                portfolio_value: 0,
                total_return_rate: 0,
                max_drawdown: 0,
                win_rate: 0,
            },
            charts: {},
            connectionStatus: 'connecting',
            errorMessage: '',
            connectionAttempts: 0,
            maxRetries: 3,
        }
    },
    computed: {
        statusText() {
            switch(this.connectionStatus) {
                case 'connected':
                    return '系统运行中';
                case 'disconnected':
                    return '连接断开';
                case 'connecting':
                    return '正在连接...';
                default:
                    return '未知状态';
            }
        }
    },
    methods: {
        formatNumber(num) {
            if (num === null || num === undefined) return '0.00';
            return Number(num).toLocaleString('zh-CN', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        },
        formatTime(timestamp) {
            return new Date(timestamp).toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
        },
        async fetchData() {
            try {
                const timestamp = new Date().getTime()
                const [summaryRes, tradingDataRes] = await Promise.all([
                    axios.get(`/api/summary-simplified?t=${timestamp}`),
                    axios.get(`/api/trading-data-simplified?t=${timestamp}`)
                ])
                
                this.connectionStatus = 'connected'
                this.errorMessage = ''
                this.connectionAttempts = 0
                this.summary = summaryRes.data
                this.updateCharts(tradingDataRes.data)
            } catch (error) {
                this.connectionAttempts++
                if (this.connectionAttempts >= this.maxRetries) {
                    this.connectionStatus = 'disconnected'
                    this.errorMessage = '无法连接到服务器'
                }
                console.error('Error fetching data:', error)
            }
        },
        initCharts() {
            // 初始化所有图表
            this.charts.return = echarts.init(document.getElementById('returnChart'))
            this.charts.assetAllocation = echarts.init(document.getElementById('assetAllocationChart'))
            this.charts.unrealizedPnl = echarts.init(document.getElementById('unrealizedPnlChart'))
            this.charts.drawdown = echarts.init(document.getElementById('drawdownChart'))
        },
        updateCharts(data) {
            // 更新收益率趋势图
            this.charts.return.setOption({
                tooltip: {
                    trigger: 'axis',
                    backgroundColor: 'rgba(255, 255, 255, 0.9)',
                    borderColor: '#ccc',
                    borderWidth: 1,
                    textStyle: {
                        color: '#333'
                    },
                    formatter: function(params) {
                        const time = new Date(params[0].name).toLocaleString('zh-CN', {
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit'
                        });
                        let result = `<div style="padding: 3px 0"><b>时间：${time}</b></div>`;
                        params.forEach(param => {
                            const value = param.value === null ? '-' : param.value.toFixed(2);
                            const marker = param.marker;
                            const color = param.color;
                            result += `<div style="padding: 3px 0">
                                ${marker} <span style="color:${color}">${param.seriesName}</span>: 
                                <b>${value}%</b>
                            </div>`;
                        });
                        return result;
                    },
                    axisPointer: {
                        type: 'cross',
                        label: {
                            backgroundColor: '#6a7985'
                        },
                        lineStyle: {
                            color: '#6e7681',
                            width: 1,
                            type: 'dashed'
                        }
                    }
                },
                legend: {
                    data: ['收益率']
                },
                xAxis: {
                    type: 'category',
                    boundaryGap: false,
                    data: data.timestamps.map(t => this.formatTime(t)),
                    axisLabel: {
                        interval: Math.floor(data.timestamps.length / 8),
                        formatter: function(value) {
                            return new Date(value).toLocaleString('zh-CN', {
                                month: '2-digit',
                                day: '2-digit',
                                hour: '2-digit',
                                minute: '2-digit'
                            });
                        }
                    }
                },
                yAxis: {
                    type: 'value',
                    name: '收益率(%)'
                },
                series: [{
                    name: '收益率',
                    data: data.return_rates,
                    type: 'line',
                    smooth: true
                }],
                grid: {
                    left: '3%',
                    right: '4%',
                    bottom: '3%',
                    containLabel: true
                }
            })

            // 更新资金分布图
            this.charts.assetAllocation.setOption({
                tooltip: {
                    trigger: 'axis',
                    backgroundColor: 'rgba(255, 255, 255, 0.9)',
                    borderColor: '#ccc',
                    borderWidth: 1,
                    textStyle: {
                        color: '#333'
                    },
                    formatter: function(params) {
                        const time = new Date(params[0].name).toLocaleString('zh-CN', {
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit'
                        });
                        let result = `<div style="padding: 3px 0"><b>时间：${time}</b></div>`;
                        params.forEach(param => {
                            const value = param.value === null ? '-' : param.value.toFixed(2);
                            const marker = param.marker;
                            const color = param.color;
                            result += `<div style="padding: 3px 0">
                                ${marker} <span style="color:${color}">${param.seriesName}</span>: 
                                <b>${value}%</b>
                            </div>`;
                        });
                        return result;
                    },
                    axisPointer: {
                        type: 'cross',
                        label: {
                            backgroundColor: '#6a7985'
                        },
                        lineStyle: {
                            color: '#6e7681',
                            width: 1,
                            type: 'dashed'
                        }
                    }
                },
                legend: {
                    data: ['现金', '持仓']
                },
                xAxis: {
                    type: 'category',
                    boundaryGap: false,
                    data: data.timestamps.map(t => this.formatTime(t)),
                    axisLabel: {
                        interval: Math.floor(data.timestamps.length / 8),
                        formatter: function(value) {
                            return new Date(value).toLocaleString('zh-CN', {
                                month: '2-digit',
                                day: '2-digit',
                                hour: '2-digit',
                                minute: '2-digit'
                            });
                        }
                    }
                },
                yAxis: {
                    type: 'value',
                    name: '金额($)'
                },
                series: [
                    {
                        name: '现金',
                        type: 'line',
                        stack: 'total',
                        areaStyle: {},
                        data: data.current_cash
                    },
                    {
                        name: '持仓',
                        type: 'line',
                        stack: 'total',
                        areaStyle: {},
                        data: data.position_values
                    }
                ],
                grid: {
                    left: '3%',
                    right: '4%',
                    bottom: '3%',
                    containLabel: true
                }
            })

            // 更新未实现盈亏图
            this.charts.unrealizedPnl.setOption({
                tooltip: {
                    trigger: 'axis',
                    backgroundColor: 'rgba(255, 255, 255, 0.9)',
                    borderColor: '#ccc',
                    borderWidth: 1,
                    textStyle: {
                        color: '#333'
                    },
                    formatter: function(params) {
                        const time = new Date(params[0].name).toLocaleString('zh-CN', {
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit'
                        });
                        let result = `<div style="padding: 3px 0"><b>时间：${time}</b></div>`;
                        params.forEach(param => {
                            const value = param.value === null ? '-' : param.value.toFixed(2);
                            const marker = param.marker;
                            const color = param.color;
                            result += `<div style="padding: 3px 0">
                                ${marker} <span style="color:${color}">${param.seriesName}</span>: 
                                <b>${value}%</b>
                            </div>`;
                        });
                        return result;
                    },
                    axisPointer: {
                        type: 'cross',
                        label: {
                            backgroundColor: '#6a7985'
                        },
                        lineStyle: {
                            color: '#6e7681',
                            width: 1,
                            type: 'dashed'
                        }
                    }
                },
                legend: {
                    data: ['未实现盈亏']
                },
                xAxis: {
                    type: 'category',
                    boundaryGap: false,
                    data: data.timestamps.map(t => this.formatTime(t)),
                    axisLabel: {
                        interval: Math.floor(data.timestamps.length / 8),
                        formatter: function(value) {
                            return new Date(value).toLocaleString('zh-CN', {
                                month: '2-digit',
                                day: '2-digit',
                                hour: '2-digit',
                                minute: '2-digit'
                            });
                        }
                    }
                },
                yAxis: {
                    type: 'value',
                    name: '未实现盈亏($)'
                },
                series: [{
                    name: '未实现盈亏',
                    data: data.unrealized_pnls,
                    type: 'line',
                    smooth: true,
                    areaStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: 'rgba(58,177,255,0.5)' },
                            { offset: 1, color: 'rgba(58,177,255,0.1)' }
                        ])
                    }
                }],
                grid: {
                    left: '3%',
                    right: '4%',
                    bottom: '3%',
                    containLabel: true
                }
            })

            // 更新最大回撤图
            this.charts.drawdown.setOption({
                tooltip: {
                    trigger: 'axis',
                    backgroundColor: 'rgba(255, 255, 255, 0.9)',
                    borderColor: '#ccc',
                    borderWidth: 1,
                    textStyle: {
                        color: '#333'
                    },
                    formatter: function(params) {
                        const time = new Date(params[0].name).toLocaleString('zh-CN', {
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit'
                        });
                        let result = `<div style="padding: 3px 0"><b>时间：${time}</b></div>`;
                        params.forEach(param => {
                            const value = param.value === null ? '-' : param.value.toFixed(2);
                            const marker = param.marker;
                            const color = param.color;
                            result += `<div style="padding: 3px 0">
                                ${marker} <span style="color:${color}">${param.seriesName}</span>: 
                                <b>${value}%</b>
                            </div>`;
                        });
                        return result;
                    },
                    axisPointer: {
                        type: 'cross',
                        label: {
                            backgroundColor: '#6a7985'
                        },
                        lineStyle: {
                            color: '#6e7681',
                            width: 1,
                            type: 'dashed'
                        }
                    }
                },
                legend: {
                    data: ['最大回撤']
                },
                xAxis: {
                    type: 'category',
                    boundaryGap: false,
                    data: data.timestamps.map(t => this.formatTime(t)),
                    axisLabel: {
                        interval: Math.floor(data.timestamps.length / 8),
                        formatter: function(value) {
                            return new Date(value).toLocaleString('zh-CN', {
                                month: '2-digit',
                                day: '2-digit',
                                hour: '2-digit',
                                minute: '2-digit'
                            });
                        }
                    }
                },
                yAxis: {
                    type: 'value',
                    name: '最大回撤(%)',
                    inverse: true
                },
                series: [{
                    name: '最大回撤',
                    data: data.max_drawdowns,
                    type: 'line',
                    smooth: true,
                    lineStyle: { color: '#ff4d4f' },
                    areaStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: 'rgba(255,77,79,0.3)' },
                            { offset: 1, color: 'rgba(255,77,79,0.1)' }
                        ])
                    }
                }],
                grid: {
                    left: '3%',
                    right: '4%',
                    bottom: '3%',
                    containLabel: true
                }
            })
        }
    },
    mounted() {
        this.initCharts()
        this.fetchData()
        // 每5秒更新一次数据
        setInterval(this.fetchData, 5000)
        
        // 监听窗口大小变化，调整图表大小
        window.addEventListener('resize', () => {
            Object.values(this.charts).forEach(chart => chart.resize())
        })
    }
}).mount('#app')
