# Local configuration inputs

Save the newest user-exported Ajaib US-stock response as:

`config/private_ajaib_us_stock.json`

This path is ignored by Git because it may contain private account or catalogue
data. The file must be the complete JSON response, including `err_message`,
`result.count`, and `result.results`; do not paste only a table or selected
symbols.

The application validates the approved status and count before storing an
immutable local SQLite snapshot. A supplied snapshot is a discovery hint and
availability reference. It does not prove that an order is possible in Ajaib,
that a security is a common stock, or that it is suitable to buy.
