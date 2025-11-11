/**
 * AuditTrailTimeline - Displays chronological audit trail events
 */

import { Clock, CheckCircle } from 'lucide-react';
import { formatDate } from '../../utils/formatting';
import type { AuditTrailEvent } from '../../types/calculations';

interface AuditTrailTimelineProps {
  auditTrail: AuditTrailEvent[];
}

export function AuditTrailTimeline({ auditTrail }: AuditTrailTimelineProps) {
  if (!auditTrail || auditTrail.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6 text-center">
        <Clock className="w-12 h-12 text-gray-400 mx-auto mb-3" />
        <p className="text-gray-500">No audit trail events available</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200">
        <h3 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
          <Clock className="w-5 h-5 text-gray-500" />
          Audit Trail
        </h3>
        <p className="text-sm text-gray-600 mt-1">
          Chronological record of calculation events
        </p>
      </div>

      {/* Timeline */}
      <div className="p-6">
        <div className="space-y-4">
          {auditTrail.map((event, index) => (
            <div key={index} className="relative">
              {/* Timeline connector */}
              {index < auditTrail.length - 1 && (
                <div className="absolute left-3 top-8 bottom-0 w-0.5 bg-gray-200" />
              )}

              {/* Event item */}
              <div className="flex gap-4">
                {/* Icon */}
                <div className="flex-shrink-0">
                  <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center relative z-10">
                    <CheckCircle className="w-4 h-4 text-blue-600" />
                  </div>
                </div>

                {/* Content */}
                <div className="flex-1 pb-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <h4 className="font-medium text-gray-800 text-sm">{event.event}</h4>
                      <p className="text-sm text-gray-600 mt-1">{event.details}</p>
                    </div>
                    <time className="flex-shrink-0 text-xs text-gray-500">
                      {formatDate(event.timestamp)}
                    </time>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
