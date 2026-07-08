export default function ReportsLoading() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-8 w-48 bg-light-border dark:bg-dark-border rounded" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-28 glass rounded-xl p-4">
            <div className="h-4 w-20 bg-light-border dark:bg-dark-border rounded mb-3" />
            <div className="h-8 w-24 bg-light-border dark:bg-dark-border rounded mb-2" />
            <div className="h-3 w-16 bg-light-border dark:bg-dark-border rounded" />
          </div>
        ))}
      </div>
    </div>
  );
}
