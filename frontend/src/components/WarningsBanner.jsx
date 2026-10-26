export default function WarningsBanner({ warnings }) {
  if (!warnings || warnings.length === 0) return null
  return (
    <div className="banner banner--warning" role="status">
      <strong>
        {warnings.length} row{warnings.length === 1 ? '' : 's'} could not be read
      </strong>
      <ul>
        {warnings.map((warning) => (
          <li key={warning}>{warning}</li>
        ))}
      </ul>
    </div>
  )
}
