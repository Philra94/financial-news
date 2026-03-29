# Editorial Graph Examples

## Line Chart

Use for one trend with one important inflection:

```md
![US core CPI is cooling only gradually](/assets/charts/us-core-cpi.svg)

*Source: BLS. Year-over-year percent change. Red marker highlights the latest release.*
```

Design notes:

- one dark line
- one red endpoint marker
- light horizontal guides only
- direct label at the latest point

## Column Chart

Use for a few category comparisons:

```md
![Cloud growth leaders remain concentrated](/assets/charts/cloud-growth-leaders.svg)

*Source: company filings. Latest reported quarterly revenue growth.*
```

Design notes:

- use neutral bars by default
- use red on only the bar the article discusses most
- sort bars by value when ranking matters

## Sparkline

Use inside a short research note when a full chart would be too heavy:

```md
![Brent crude has stabilized after the recent spike](/assets/charts/brent-sparkline.svg)

*Source: market data, trailing three months.*
```

Design notes:

- no full axis furniture
- one endpoint label
- no legend

## When Not To Chart

Prefer prose or a table instead of a chart when:

- the argument depends on caveats
- the dataset is tiny and fully readable as text
- the values are approximate or disputed
- the chart needs more than one legend and several colors to work
