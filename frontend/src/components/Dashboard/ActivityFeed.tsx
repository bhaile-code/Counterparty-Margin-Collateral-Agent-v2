import { Upload, FileCheck } from 'lucide-react';
import { formatRelativeTime } from '../../utils/formatting';
import type { DocumentListItem } from '../../types/documents';

interface ActivityItem {
  id: string;
  type: 'upload' | 'extraction' | 'calculation';
  description: string;
  timestamp: string;
  icon: React.ReactNode;
  iconBg: string;
}

interface ActivityFeedProps {
  documents: DocumentListItem[];
  maxItems?: number;
}

export function ActivityFeed({ documents, maxItems = 5 }: ActivityFeedProps) {
  // Helper function to format party display name for activity feed
  // For activity descriptions, showing filename when parties aren't available is more informative
  const getPartyDisplayName = (doc: DocumentListItem): string => {
    if (doc.party_a && doc.party_b) {
      return `${doc.party_a} • ${doc.party_b}`;
    }
    if (doc.party_a || doc.party_b) {
      const partyA = doc.party_a || 'Unknown';
      const partyB = doc.party_b || 'Unknown';
      return `${partyA} • ${partyB}`;
    }
    // Show filename for activity feed context (more informative in activity descriptions)
    return doc.filename;
  };

  // Convert documents to activity items
  const activities: ActivityItem[] = documents
    .map((doc) => {
      const items: ActivityItem[] = [];

      // Upload activity
      items.push({
        id: `upload-${doc.document_id}`,
        type: 'upload',
        description: `Uploaded ${doc.filename}`,
        timestamp: doc.uploaded_at,
        icon: <Upload className="w-4 h-4" />,
        iconBg: 'bg-blue-100 text-blue-600'
      });

      // Extraction activity (if processed)
      if (doc.processing_status?.mapped_to_csa_terms) {
        items.push({
          id: `extraction-${doc.document_id}`,
          type: 'extraction',
          description: `Extracted CSA terms from ${getPartyDisplayName(doc)}`,
          timestamp: doc.uploaded_at, // Using upload time as proxy
          icon: <FileCheck className="w-4 h-4" />,
          iconBg: 'bg-green-100 text-green-600'
        });
      }

      return items;
    })
    .flat()
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    .slice(0, maxItems);

  if (activities.length === 0) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Recent Activity
        </h2>
        <p className="text-sm text-gray-500 text-center py-8">
          No recent activity
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">
        Recent Activity
      </h2>

      <div className="flow-root">
        <ul className="-mb-8">
          {activities.map((activity, idx) => (
            <li key={activity.id}>
              <div className="relative pb-8">
                {/* Connecting line */}
                {idx !== activities.length - 1 && (
                  <span
                    className="absolute left-4 top-5 -ml-px h-full w-0.5 bg-gray-200"
                    aria-hidden="true"
                  />
                )}

                <div className="relative flex items-start space-x-3">
                  {/* Icon */}
                  <div>
                    <div
                      className={`h-8 w-8 rounded-full flex items-center justify-center ${activity.iconBg}`}
                    >
                      {activity.icon}
                    </div>
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div>
                      <p className="text-sm text-gray-900">
                        {activity.description}
                      </p>
                      <p className="mt-0.5 text-xs text-gray-500">
                        {formatRelativeTime(activity.timestamp)}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
