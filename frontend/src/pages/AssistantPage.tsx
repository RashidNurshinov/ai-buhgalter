/**
 * Страница ИИ-ассистента — чат с бухгалтерским ИИ.
 */
import { useState, useRef, useEffect } from 'react';
import {
  Typography,
  Card,
  Input,
  Button,
  Space,
  Spin,
  Tag,
  List,
  Divider,
  Badge,
} from 'antd';
import {
  SendOutlined,
  RobotOutlined,
  UserOutlined,
  CheckOutlined,
  CloseOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { agentApi } from '@/api/endpoints';
import ReactMarkdown from 'react-markdown';
import type { AgentChatResponse, AgentConfirmation, AgentAction } from '@/types';

const { Title, Text } = Typography;
const { TextArea } = Input;

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  actions?: AgentAction[];
  confirmations?: AgentConfirmation[];
}

const QUICK_COMMANDS = [
  { label: '📊 Сводка по финансам', command: 'Покажи сводку по финансам за текущий квартал' },
  { label: '📅 Ближайшие дедлайны', command: 'Какие ближайшие налоговые дедлайны?' },
  { label: '🔄 Неподтверждённые операции', command: 'Покажи неподтверждённые операции' },
  { label: '🧮 Расчёт налога', command: 'Рассчитай налог УСН за текущий квартал' },
  { label: '📖 Статус КУДиР', command: 'Какой статус КУДиР?' },
];

export default function AssistantPage() {
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content:
        'Здравствуйте! Я ваш ИИ-бухгалтер. Задайте вопрос о налогах, операциях, документах или воспользуйтесь быстрыми командами ниже.',
      timestamp: new Date(),
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Pending confirmations
  const { data: confirmations } = useQuery({
    queryKey: ['agent-confirmations'],
    queryFn: () => agentApi.getConfirmations(),
    select: (res) => res.data as AgentConfirmation[],
    refetchInterval: 30000,
  });

  // Chat mutation
  const chatMutation = useMutation({
    mutationFn: (msg: string) =>
      agentApi.chat({ message: msg }),
    onSuccess: (res) => {
      const data = res.data as AgentChatResponse;
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.response,
          timestamp: new Date(),
          actions: data.actions_taken,
          confirmations: data.confirmations_requested,
        },
      ]);
      // Refresh confirmations if new ones were created
      if (data.confirmations_requested?.length) {
        queryClient.invalidateQueries({ queryKey: ['agent-confirmations'] });
      }
    },
    onError: () => {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: '⚠️ Произошла ошибка при обработке запроса. Попробуйте ещё раз.',
          timestamp: new Date(),
        },
      ]);
    },
  });

  // Confirm/reject action
  const confirmMutation = useMutation({
    mutationFn: ({
      confirmationId,
      approved,
    }: {
      confirmationId: string;
      approved: boolean;
    }) => agentApi.confirm(confirmationId, approved),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent-confirmations'] });
    },
  });

  const handleSend = () => {
    const text = inputValue.trim();
    if (!text) return;

    setMessages((prev) => [
      ...prev,
      { role: 'user', content: text, timestamp: new Date() },
    ]);
    setInputValue('');
    chatMutation.mutate(text);
  };

  const handleQuickCommand = (command: string) => {
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: command, timestamp: new Date() },
    ]);
    chatMutation.mutate(command);
  };

  const pendingConfirmations: AgentConfirmation[] = (confirmations || []).filter(
    (c) => c.status === 'pending' || c.user_response === null,
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 180px)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>
          🤖 ИИ-Ассистент
        </Title>
        {pendingConfirmations.length > 0 && (
          <Badge count={pendingConfirmations.length}>
            <Tag color="orange">Ожидают подтверждения</Tag>
          </Badge>
        )}
      </div>

      <div style={{ display: 'flex', gap: 16, flex: 1, minHeight: 0 }}>
        {/* Chat area */}
        <Card
          style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
          bodyStyle={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            padding: 0,
            overflow: 'hidden',
          }}
        >
          {/* Messages */}
          <div
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: 16,
            }}
          >
            {messages.map((msg, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  gap: 8,
                  marginBottom: 16,
                  flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                }}
              >
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: '50%',
                    background:
                      msg.role === 'user' ? '#1677ff' : '#f0f0f0',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  {msg.role === 'user' ? (
                    <UserOutlined style={{ color: '#fff' }} />
                  ) : (
                    <RobotOutlined style={{ color: '#1677ff' }} />
                  )}
                </div>
                <div
                  style={{
                    maxWidth: '75%',
                    padding: '10px 14px',
                    borderRadius: 12,
                    background:
                      msg.role === 'user' ? '#1677ff' : '#f5f5f5',
                    color: msg.role === 'user' ? '#fff' : 'inherit',
                  }}
                >
                  {msg.role === 'assistant' ? (
                    <div className="markdown-content">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                  )}
                  {/* Show actions taken */}
                  {msg.actions && msg.actions.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <Divider style={{ margin: '8px 0' }} />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        Выполненные действия:
                      </Text>
                      {msg.actions.map((action, ai) => (
                        <div
                          key={ai}
                          style={{
                            marginTop: 4,
                            padding: 8,
                            background: 'rgba(0,0,0,0.04)',
                            borderRadius: 6,
                          }}
                        >
                          <Space size="small">
                            <Tag color="blue">{action.action_type}</Tag>
                            {action.tool_name && (
                              <Text style={{ fontSize: 12 }}>
                                {action.tool_name}
                              </Text>
                            )}
                            <Tag
                              color={action.status === 'completed' ? 'green' : 'orange'}
                              style={{ fontSize: 10 }}
                            >
                              {action.status}
                            </Tag>
                          </Space>
                        </div>
                      ))}
                    </div>
                  )}
                  {/* Show confirmations requested */}
                  {msg.confirmations && msg.confirmations.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <Divider style={{ margin: '8px 0' }} />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        ❓ Требуется подтверждение:
                      </Text>
                      {msg.confirmations.map((conf, ci) => (
                        <div
                          key={ci}
                          style={{
                            marginTop: 4,
                            padding: 8,
                            background: 'rgba(250,173,20,0.1)',
                            borderRadius: 6,
                          }}
                        >
                          <Text style={{ fontSize: 12 }}>{conf.question}</Text>
                        </div>
                      ))}
                    </div>
                  )}
                  <div
                    style={{
                      fontSize: 10,
                      opacity: 0.6,
                      marginTop: 4,
                      textAlign: msg.role === 'user' ? 'right' : 'left',
                    }}
                  >
                    {msg.timestamp.toLocaleTimeString('ru-RU', {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </div>
                </div>
              </div>
            ))}
            {chatMutation.isPending && (
              <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: '50%',
                    background: '#f0f0f0',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <RobotOutlined style={{ color: '#1677ff' }} />
                </div>
                <div
                  style={{
                    padding: '12px 16px',
                    borderRadius: 12,
                    background: '#f5f5f5',
                  }}
                >
                  <Spin size="small" /> <Text type="secondary">Думаю…</Text>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick commands */}
          <div
            style={{
              padding: '8px 16px',
              borderTop: '1px solid #f0f0f0',
              overflowX: 'auto',
              whiteSpace: 'nowrap',
            }}
          >
            <Space size="small">
              {QUICK_COMMANDS.map((cmd) => (
                <Button
                  key={cmd.command}
                  size="small"
                  onClick={() => handleQuickCommand(cmd.command)}
                  disabled={chatMutation.isPending}
                >
                  {cmd.label}
                </Button>
              ))}
            </Space>
          </div>

          {/* Input */}
          <div style={{ padding: 16, borderTop: '1px solid #f0f0f0' }}>
            <Space.Compact style={{ width: '100%' }}>
              <TextArea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="Задайте вопрос ИИ-бухгалтеру…"
                autoSize={{ minRows: 1, maxRows: 4 }}
                onPressEnter={(e) => {
                  if (!e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                disabled={chatMutation.isPending}
                style={{ borderRadius: '6px 0 0 6px' }}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSend}
                loading={chatMutation.isPending}
                style={{ height: 'auto', borderRadius: '0 6px 6px 0' }}
              />
            </Space.Compact>
            <Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
              Enter — отправить, Shift+Enter — новая строка
            </Text>
          </div>
        </Card>

        {/* Confirmations sidebar (only if there are pending) */}
        {pendingConfirmations.length > 0 && (
          <Card
            title={
              <Space>
                <QuestionCircleOutlined />
                Подтверждения
              </Space>
            }
            style={{ width: 320, flexShrink: 0 }}
            bodyStyle={{ overflowY: 'auto' }}
          >
            <List
              dataSource={pendingConfirmations}
              renderItem={(item) => (
                <List.Item
                  actions={[
                    <Button
                      key="approve"
                      type="primary"
                      size="small"
                      icon={<CheckOutlined />}
                      onClick={() =>
                        confirmMutation.mutate({
                          confirmationId: item.id,
                          approved: true,
                        })
                      }
                    >
                      Да
                    </Button>,
                    <Button
                      key="reject"
                      size="small"
                      danger
                      icon={<CloseOutlined />}
                      onClick={() =>
                        confirmMutation.mutate({
                          confirmationId: item.id,
                          approved: false,
                        })
                      }
                    >
                      Нет
                    </Button>,
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Tag color="orange">Подтверждение</Tag>
                    }
                    description={item.question}
                  />
                </List.Item>
              )}
            />
          </Card>
        )}
      </div>
    </div>
  );
}